# Stage 1: compile. Has the whole Go toolchain (~300MB).
FROM golang:1.25-alpine AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY *.go ./
RUN go test ./... && CGO_ENABLED=0 go build -o /user-event .

# Stage 2: run. Just the compiled binary on a tiny base (~10MB).
# This "multi-stage build" is why Go services ship so small.
FROM alpine:3.20
COPY --from=build /user-event /user-event
EXPOSE 8002
CMD ["/user-event"]
