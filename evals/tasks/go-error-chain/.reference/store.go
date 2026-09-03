package statusboard

import (
	"context"
	"errors"
	"fmt"
)

// ErrRegionDown reports that an entire region is unavailable.
var ErrRegionDown = errors.New("region down")

// BackendError describes a failure of one backend node.
type BackendError struct {
	Endpoint string
	Code     int
	Err      error
}

func (e *BackendError) Error() string {
	return fmt.Sprintf("backend %s returned code %d: %v", e.Endpoint, e.Code, e.Err)
}

func (e *BackendError) Unwrap() error { return e.Err }

// simulateBackend stands in for one call to the region status backend.
// It is deterministic: the fixture table below never changes.
func simulateBackend(ctx context.Context, region string) (string, error) {
	switch region {
	case "eu-west-1", "ap-south-1":
		return "", ErrRegionDown
	case "us-east-2", "sa-east-1":
		return "", &BackendError{
			Endpoint: "status.internal.example.net",
			Code:     503,
			Err:      errors.New("connection refused"),
		}
	default:
		return "operational", nil
	}
}

// FetchStatus queries the simulated backend for the region's status.
func FetchStatus(ctx context.Context, region string) (string, error) {
	st, err := simulateBackend(ctx, region)
	if err != nil {
		return "", fmt.Errorf("fetching region status: %w", err)
	}
	return st, nil
}
