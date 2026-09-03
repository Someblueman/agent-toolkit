package statusboard

import (
	"context"
	"errors"
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

// Handle probes one region and reports its status.
func (h *Handler) Handle(ctx context.Context, region string) (string, error) {
	st, err := h.svc.CheckRegion(ctx, region)
	if err != nil {
		if errors.Is(err, ErrRegionDown) {
			return "", ErrRegionDown
		}
		return "", fmt.Errorf("status probe for %s: %v", region, err)
	}
	return st, nil
}
