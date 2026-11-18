package main

import "testing"

// Table-driven test: the standard Go style. One list of cases, one loop.
func TestValidate(t *testing.T) {
	cases := []struct {
		name    string
		event   Event
		wantErr bool
	}{
		{"valid", Event{UserID: "u1", VideoID: "v1", WatchMs: 500}, false},
		{"missing user", Event{VideoID: "v1"}, true},
		{"missing video", Event{UserID: "u1"}, true},
		{"negative watch time", Event{UserID: "u1", VideoID: "v1", WatchMs: -1}, true},
	}

	for _, c := range cases {
		err := c.event.Validate()
		gotErr := err != nil
		if gotErr != c.wantErr {
			t.Errorf("%s: wantErr=%v, got err=%v", c.name, c.wantErr, err)
		}
	}
}
