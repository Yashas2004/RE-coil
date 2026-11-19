package main

import "hash/fnv"

// InHoldout puts a fixed slice of users into the CONTROL group of an A/B test.
//
// Control users get a plain trending feed (no model). Everyone else gets the
// model. Comparing the two groups' watch rates at the SAME time is a fair test:
// a "before vs after" comparison can be fooled by anything else that changed
// in between, but two groups living side by side can't.
//
// Hashing the user_id (instead of flipping a coin per request) keeps each user
// in the same group forever. If a user bounced between groups, their behaviour
// in one would leak into the other.
func InHoldout(userID string, percent int) bool {
	hasher := fnv.New32a()
	hasher.Write([]byte(userID))
	bucket := int(hasher.Sum32() % 100)
	return bucket < percent
}
