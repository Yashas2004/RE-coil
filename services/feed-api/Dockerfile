FROM golang:1.25-alpine AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY *.go ./
RUN go test ./... && CGO_ENABLED=0 go build -o /feed-api .

FROM alpine:3.20
COPY --from=build /feed-api /feed-api
EXPOSE 8005
CMD ["/feed-api"]
