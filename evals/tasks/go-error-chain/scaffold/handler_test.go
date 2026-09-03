package statusboard_test

import (
	"context"
	"testing"

	"statusboard"
)

// Smoke test: healthy regions must keep working.
func TestHealthyRegionSmoke(t *testing.T) {
	h := statusboard.NewHandler()
	st, err := h.Handle(context.Background(), "us-west-1")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if st != "operational" {
		t.Fatalf("unexpected status: %q", st)
	}
}
