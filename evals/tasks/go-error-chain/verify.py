#!/usr/bin/env python3
"""Mechanical scorer for go-error-chain.

1. Drops hidden behavioral tests into the module (removed afterwards).
2. Runs `go vet ./...` and `go test ./...` offline.
3. Runs structural gates over non-test sources (AST + type info via a
   temporary checker program compiled with `go run`).

Prints METRICS {...} as the last stdout line; exit 0 = pass.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HIDDEN_TESTS = r'''package statusboard_test

import (
	"context"
	"errors"
	"testing"

	"statusboard"
)

func TestOutageRegionsAreDetectable(t *testing.T) {
	h := statusboard.NewHandler()
	for _, region := range []string{"eu-west-1", "ap-south-1"} {
		_, err := h.Handle(context.Background(), region)
		if err == nil {
			t.Fatalf("%s: expected an error", region)
		}
		if !errors.Is(err, statusboard.ErrRegionDown) {
			t.Fatalf("%s: outage not detectable via errors.Is(err, ErrRegionDown); got %q", region, err)
		}
		var be *statusboard.BackendError
		if errors.As(err, &be) {
			t.Fatalf("%s: outage misreported as backend failure: %v", region, err)
		}
		want := "status probe for " + region + ": checking region " + region + ": fetching region status: region down"
		if err.Error() != want {
			t.Fatalf("%s: message mismatch\n got: %s\nwant: %s", region, err.Error(), want)
		}
	}
}

func TestBackendFailuresAreExtractable(t *testing.T) {
	h := statusboard.NewHandler()
	for _, region := range []string{"us-east-2", "sa-east-1"} {
		_, err := h.Handle(context.Background(), region)
		if err == nil {
			t.Fatalf("%s: expected an error", region)
		}
		var be *statusboard.BackendError
		if !errors.As(err, &be) {
			t.Fatalf("%s: backend failure not extractable via errors.As(err, &be); got %q", region, err)
		}
		if be.Code != 503 || be.Endpoint != "status.internal.example.net" {
			t.Fatalf("%s: unexpected BackendError fields: %+v", region, be)
		}
		if be.Err == nil || be.Err.Error() != "connection refused" {
			t.Fatalf("%s: BackendError lost the node's own detail: %v", region, be.Err)
		}
		if errors.Is(err, statusboard.ErrRegionDown) {
			t.Fatalf("%s: backend failure misreported as region outage: %v", region, err)
		}
		want := "status probe for " + region + ": checking region " + region + ": fetching region status: backend status.internal.example.net returned code 503: connection refused"
		if err.Error() != want {
			t.Fatalf("%s: message mismatch\n got: %s\nwant: %s", region, err.Error(), want)
		}
	}
}

func TestHealthyRegionsUnaffected(t *testing.T) {
	h := statusboard.NewHandler()
	for _, region := range []string{"us-west-1", "eu-north-3"} {
		st, err := h.Handle(context.Background(), region)
		if err != nil {
			t.Fatalf("%s: unexpected error: %v", region, err)
		}
		if st != "operational" {
			t.Fatalf("%s: unexpected status %q", region, st)
		}
	}
}
'''

CHECKER = r'''// checker enforces the structural gates for go-error-chain over non-test
// sources:
//   A. a %v/%s format verb applied to an error-typed value in fmt.Errorf or
//      fmt.Sprintf, outside an Error() string method, and
//   B. the sentinel ErrRegionDown returned bare or used to construct a new
//      error outside the store layer (the file declaring FetchStatus), and
//   C. BackendError composite literals constructed outside the store layer.
package main

import (
	"fmt"
	"go/ast"
	"go/importer"
	"go/parser"
	"go/token"
	"go/types"
	"os"
	"path/filepath"
	"strings"
)

type violation struct {
	pos string
	msg string
}

var violations []violation

func report(fset *token.FileSet, pos token.Pos, format string, args ...interface{}) {
	violations = append(violations, violation{
		pos: fset.Position(pos).String(),
		msg: fmt.Sprintf(format, args...),
	})
}

func declaresFunc(f *ast.File, name string) bool {
	for _, d := range f.Decls {
		if fd, ok := d.(*ast.FuncDecl); ok && fd.Name.Name == name {
			return true
		}
	}
	return false
}

type verb struct {
	ch   byte
	star bool // '*' width: consumes an extra argument before the value
}

func parseVerbs(format string) []verb {
	var out []verb
	for i := 0; i < len(format); i++ {
		if format[i] != '%' {
			continue
		}
		i++
		if i >= len(format) {
			break
		}
		if format[i] == '%' {
			continue
		}
		vb := verb{}
		for i < len(format) {
			c := format[i]
			if (c >= '0' && c <= '9') || c == '.' || c == '+' || c == '-' || c == ' ' || c == '#' || c == '[' || c == ']' {
				i++
				continue
			}
			if c == '*' && !vb.star {
				vb.star = true
				i++
				continue
			}
			break
		}
		if i >= len(format) {
			break
		}
		vb.ch = format[i]
		out = append(out, vb)
	}
	return out
}

func isErrishName(name string) bool {
	lower := strings.ToLower(name)
	return strings.HasPrefix(lower, "err") || strings.HasSuffix(lower, "err")
}

type checker struct {
	fset        *token.FileSet
	info        *types.Info
	sentinel    types.Object
	errorIface  *types.Interface
	spans       []funcSpan
}

type funcSpan struct {
	node   ast.Node
	exempt bool // Error() string method body
}

func (c *checker) enclosing(pos token.Pos) *funcSpan {
	for i := range c.spans {
		s := &c.spans[i]
		if s.node.Pos() <= pos && pos < s.node.End() {
			return s
		}
	}
	return nil
}

func (c *checker) isErrorVal(e ast.Expr) bool {
	if t := c.info.TypeOf(e); t != nil {
		if c.errorIface != nil && types.Implements(t, c.errorIface) {
			return true
		}
		return false
	}
	// Type info unavailable: fall back to a naming heuristic.
	switch v := e.(type) {
	case *ast.Ident:
		return isErrishName(v.Name)
	case *ast.SelectorExpr:
		return isErrishName(v.Sel.Name)
	}
	return false
}

func (c *checker) isSentinel(e ast.Expr) bool {
	id, ok := e.(*ast.Ident)
	if !ok || id.Name != "ErrRegionDown" {
		return false
	}
	if o, ok := c.info.Uses[id]; ok && c.sentinel != nil && o != c.sentinel {
		return false // same-named ident resolving elsewhere
	}
	return true
}

func (c *checker) typeOf(e ast.Expr) string {
	t := c.info.TypeOf(e)
	if t == nil {
		return "?"
	}
	return t.String()
}

func main() {
	if len(os.Args) != 2 {
		fmt.Fprintln(os.Stderr, "usage: checker <workspace>")
		os.Exit(2)
	}
	root := os.Args[1]
	fset := token.NewFileSet()
	var files []*ast.File
	storeFile := ""

	err := filepath.WalkDir(root, func(path string, d os.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if d.IsDir() {
			switch d.Name() {
			case ".git", "vendor", "testdata":
				return filepath.SkipDir
			}
			return nil
		}
		name := d.Name()
		if !strings.HasSuffix(name, ".go") || strings.HasSuffix(name, "_test.go") {
			return nil
		}
		f, perr := parser.ParseFile(fset, path, nil, 0)
		if perr != nil {
			return fmt.Errorf("parse %s: %v", path, perr)
		}
		files = append(files, f)
		if declaresFunc(f, "FetchStatus") {
			storeFile = path
		}
		return nil
	})
	if err != nil {
		fmt.Fprintf(os.Stderr, "checker: %v\n", err)
		os.Exit(2)
	}
	if len(files) == 0 {
		fmt.Fprintln(os.Stderr, "checker: no non-test Go sources found")
		os.Exit(2)
	}

	info := &types.Info{
		Types: map[ast.Expr]types.TypeAndValue{},
		Uses:  map[*ast.Ident]types.Object{},
		Defs:  map[*ast.Ident]types.Object{},
	}
	c := &checker{fset: fset, info: info}
	conf := types.Config{Importer: importer.ForCompiler(fset, "source", nil)}
	conf.Error = func(error) {} // tolerate type errors; compile errors fail go test anyway

	byDir := map[string][]*ast.File{}
	var dirs []string
	for _, f := range files {
		dir := filepath.Dir(fset.Position(f.Pos()).Filename)
		if _, seen := byDir[dir]; !seen {
			dirs = append(dirs, dir)
		}
		byDir[dir] = append(byDir[dir], f)
	}
	for _, dir := range dirs {
		if pkg, _ := conf.Check(dir, fset, byDir[dir], info); pkg != nil {
			if o := pkg.Scope().Lookup("ErrRegionDown"); o != nil && c.sentinel == nil {
				c.sentinel = o
			}
		}
	}
	if eiface := types.Universe.Lookup("error"); eiface != nil {
		if iface, ok := eiface.Type().Underlying().(*types.Interface); ok {
			c.errorIface = iface
		}
	}

	for _, f := range files {
		for _, d := range f.Decls {
			fd, ok := d.(*ast.FuncDecl)
			if !ok {
				continue
			}
			exempt := fd.Recv != nil && fd.Name.Name == "Error" && fd.Type.Params.NumFields() == 0
			c.spans = append(c.spans, funcSpan{node: fd, exempt: exempt})
		}
	}

	for _, f := range files {
		path := fset.Position(f.Pos()).Filename
		isStore := path == storeFile
		ast.Inspect(f, func(n ast.Node) bool {
			switch v := n.(type) {
			case *ast.CallExpr:
				sel, ok := v.Fun.(*ast.SelectorExpr)
				if !ok {
					return true
				}
				if id, ok := sel.X.(*ast.Ident); !ok || id.Name != "fmt" {
					return true
				}
				if sel.Sel.Name != "Errorf" && sel.Sel.Name != "Sprintf" {
					return true
				}
				if len(v.Args) == 0 {
					return true
				}
				lit, ok := v.Args[0].(*ast.BasicLit)
				if !ok || lit.Kind != token.STRING {
					return true
				}
				format := strings.Trim(lit.Value, "`\"")
				argIdx := 1
				for _, vb := range parseVerbs(format) {
					if vb.star {
						argIdx++
					}
					if argIdx >= len(v.Args) {
						break
					}
					arg := v.Args[argIdx]
					argIdx++
					if vb.ch == 'v' || vb.ch == 's' {
						if c.isErrorVal(arg) {
							sp := c.enclosing(v.Pos())
							if sp == nil || !sp.exempt {
								report(fset, arg.Pos(),
									"format verb '%%%c' applied to an error value (type %s) in fmt.%s; error values must be propagated with '%%w' so callers can inspect them",
									vb.ch, c.typeOf(arg), sel.Sel.Name)
							}
						}
					}
					if c.isSentinel(arg) && !isStore {
						report(fset, arg.Pos(),
							"sentinel ErrRegionDown used to construct an error outside the store layer; report the failure that was actually received")
					}
				}
			case *ast.ReturnStmt:
				if isStore {
					return true
				}
				for _, res := range v.Results {
					if c.isSentinel(res) {
						report(fset, res.Pos(),
							"bare return of sentinel ErrRegionDown outside the store layer drops the received failure and its context")
					}
				}
			case *ast.CompositeLit:
				if isStore {
					return true
				}
				var typeName string
				switch t := v.Type.(type) {
				case *ast.Ident:
					typeName = t.Name
				case *ast.SelectorExpr:
					typeName = t.Sel.Name
				case *ast.StarExpr:
					if id, ok := t.X.(*ast.Ident); ok {
						typeName = id.Name
					} else if s, ok := t.X.(*ast.SelectorExpr); ok {
						typeName = s.Sel.Name
					}
				}
				if typeName == "BackendError" {
					report(fset, v.Pos(),
						"BackendError constructed outside the store layer; propagate the error that was actually received")
				}
			}
			return true
		})
	}

	if len(violations) > 0 {
		for _, v := range violations {
			fmt.Printf("VIOLATION %s: %s\n", v.pos, v.msg)
		}
		os.Exit(1)
	}
	fmt.Println("STRUCTURAL_CLEAN")
}
'''

PASS = True


def fail(msg: str):
    global PASS
    PASS = False
    print(f"FAIL: {msg}", file=sys.stderr)


def go_env() -> dict:
    env = dict(os.environ)
    env.update({
        "GOFLAGS": "-mod=mod",
        "GO111MODULE": "on",
        "GOPROXY": "off",
        "GOTOOLCHAIN": "local",
        "GOWORK": "off",
    })
    return env


def run(cmd: list, cwd: str) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, env=go_env(), capture_output=True,
                          text=True, timeout=180)


def main() -> int:
    ws = os.getcwd()
    go = shutil.which("go")
    vet_ok = test_ok = clean = False

    if go is None:
        fail("go toolchain not found on PATH")
    else:
        hidden = os.path.join(ws, "zz_hidden_chain_test.go")
        with open(hidden, "w", encoding="utf-8") as f:
            f.write(HIDDEN_TESTS)
        try:
            r = run([go, "vet", "./..."], ws)
            vet_ok = r.returncode == 0
            if not vet_ok:
                fail(f"go vet ./... failed:\n{r.stdout}\n{r.stderr}")

            r = run([go, "test", "./..."], ws)
            test_ok = r.returncode == 0
            if not test_ok:
                fail(f"go test ./... failed:\n{r.stdout}\n{r.stderr}")

            # Structural gates over non-test sources.
            with tempfile.TemporaryDirectory() as td:
                with open(os.path.join(td, "checker.go"), "w", encoding="utf-8") as f:
                    f.write(CHECKER)
                with open(os.path.join(td, "go.mod"), "w", encoding="utf-8") as f:
                    f.write("module checker\n\ngo 1.21\n")
                r = run([go, "run", ".", ws], td)
                clean = r.returncode == 0
                if not clean:
                    fail(f"structural gate violation:\n{(r.stdout + r.stderr).strip()}")
        finally:
            if os.path.exists(hidden):
                os.remove(hidden)

    print("METRICS " + json.dumps({
        "pass": int(PASS),
        "go_vet": int(vet_ok),
        "go_test": int(test_ok),
        "structural_clean": int(clean),
    }))
    return 0 if PASS else 1


if __name__ == "__main__":
    sys.exit(main())
