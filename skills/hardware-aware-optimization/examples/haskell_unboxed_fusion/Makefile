GHC ?= ghc
GHCFLAGS ?= -O2 -fworker-wrapper -rtsopts

all: HaskellBench

HaskellBench: HaskellBench.hs
	$(GHC) $(GHCFLAGS) HaskellBench.hs -o HaskellBench

run: HaskellBench
	./HaskellBench +RTS -s

clean:
	rm -f HaskellBench HaskellBench.hi HaskellBench.o

.PHONY: all run clean
