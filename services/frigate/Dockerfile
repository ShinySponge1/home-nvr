ARG GO2RTC_BUILDER_IMAGE=golang:1.27.3-alpine3.23@sha256:8a5046497cda39860b832ffdbe8dd66018a0f05bb01352f533a36e7e2ced66a0
ARG FRIGATE_BASE_IMAGE=ghcr.io/blakeblackshear/frigate:0.18.2@sha256:fd60f99ffd4eb6c42360ed4e14953e270586f239309ab3983e55b2e97ffac09a

FROM ${GO2RTC_BUILDER_IMAGE} AS go2rtc-build
ARG TARGETARCH
WORKDIR /src
RUN apk add --no-cache git
ADD --checksum=sha256:10027a1558746e02c9adc22ceea8ee5ad29a19e156d3dded23404103f0e7c636 \
    https://codeload.github.com/AlexxIT/go2rtc/tar.gz/7c05066c90ab6ad1fccb506d5f0408aa31ebe60f \
    /tmp/go2rtc.tar.gz
RUN tar -xzf /tmp/go2rtc.tar.gz --strip-components=1 && rm /tmp/go2rtc.tar.gz
COPY go2rtc-security.patch /tmp/go2rtc-security.patch
RUN git apply --check /tmp/go2rtc-security.patch \
    && git apply /tmp/go2rtc-security.patch \
    && test "$(go list -mod=readonly -m -f '{{.Version}}' golang.org/x/net)" = "v0.62.0" \
    && go test -mod=readonly -count=1 ./pkg/tcp \
    && go test -mod=readonly -run ContentLength -count=100 ./pkg/tcp \
    && go vet -mod=readonly ./pkg/tcp \
    && mkdir -p /out \
    && CGO_ENABLED=0 GOOS=linux GOARCH="${TARGETARCH:-amd64}" \
       go build -mod=readonly -trimpath -ldflags "-s -w" -o /out/go2rtc .

FROM ${FRIGATE_BASE_IMAGE}
LABEL org.opencontainers.image.title="Frigate go2rtc security overlay" \
      org.opencontainers.image.version="0.18.2-security.1" \
      org.opencontainers.image.source="https://github.com/ShinySponge1/home-nvr" \
      org.opencontainers.image.revision="7c05066c90ab6ad1fccb506d5f0408aa31ebe60f"
COPY --from=go2rtc-build --chmod=0555 /out/go2rtc /usr/local/go2rtc/bin/go2rtc
