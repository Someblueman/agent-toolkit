package statusboard

import (
	"context"
	"fmt"
)

// Service coordinates region status checks.
type Service struct{}

// CheckRegion returns the operational status of a region.
func (s *Service) CheckRegion(ctx context.Context, region string) (string, error) {
	st, err := FetchStatus(ctx, region)
	if err != nil {
		return "", fmt.Errorf("checking region %s: %v", region, err)
	}
	return st, nil
}
