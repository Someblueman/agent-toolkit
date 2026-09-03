package statusboard

import (
	"context"
	"fmt"
)

// Handler is the API-facing layer for status probes.
type Handler struct {
	svc *Service
}

// NewHandler wires the handler with its dependencies.
func NewHandler() *Handler {
	return &Handler{svc: &Service{}}
}

// Handle probes one region and reports its status. Failure classification
// stays available to callers: the received error is reported as-is, with
// this layer's context prefixed, so errors.Is/errors.As reach the store's
// sentinel and typed error from anywhere above.
func (h *Handler) Handle(ctx context.Context, region string) (string, error) {
	st, err := h.svc.CheckRegion(ctx, region)
	if err != nil {
		return "", fmt.Errorf("status probe for %s: %w", region, err)
	}
	return st, nil
}
