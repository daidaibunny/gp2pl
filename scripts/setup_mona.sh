#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXTERNAL_DIR="${ROOT_DIR}/.external"
MONA_VERSION="1.4-18"
MONA_TARBALL="mona-${MONA_VERSION}.tar.gz"
MONA_URL="https://www.brics.dk/mona/download/${MONA_TARBALL}"
MONA_SHA256="ece10e1e257dcae48dd898ed3da48f550c6b590f8e5c5a6447d0f384ac040e4c"
MONA_SOURCE_DIR="${EXTERNAL_DIR}/mona-1.4"

verify_sha256() {
	local file="$1"
	local expected="$2"
	local actual
	if command -v shasum >/dev/null 2>&1; then
		actual="$(shasum -a 256 "${file}" | awk '{print $1}')"
	elif command -v sha256sum >/dev/null 2>&1; then
		actual="$(sha256sum "${file}" | awk '{print $1}')"
	else
		printf '[mona] no SHA-256 utility found; install shasum or sha256sum\n' >&2
		exit 1
	fi
	if [[ "${actual}" != "${expected}" ]]; then
		printf '[mona] checksum mismatch file=%s expected=%s actual=%s\n' \
			"${file}" "${expected}" "${actual}" >&2
		exit 1
	fi
}

mkdir -p "${EXTERNAL_DIR}"

if [[ ! -f "${EXTERNAL_DIR}/${MONA_TARBALL}" ]]; then
	printf '[mona] downloading %s\n' "${MONA_URL}"
	curl -fL "${MONA_URL}" -o "${EXTERNAL_DIR}/${MONA_TARBALL}"
else
	printf '[mona] using existing tarball %s\n' "${EXTERNAL_DIR}/${MONA_TARBALL}"
fi

verify_sha256 "${EXTERNAL_DIR}/${MONA_TARBALL}" "${MONA_SHA256}"

if [[ ! -d "${MONA_SOURCE_DIR}" ]]; then
	printf '[mona] extracting %s\n' "${EXTERNAL_DIR}/${MONA_TARBALL}"
	tar -xzf "${EXTERNAL_DIR}/${MONA_TARBALL}" -C "${EXTERNAL_DIR}"
else
	printf '[mona] using existing source tree %s\n' "${MONA_SOURCE_DIR}"
fi

printf '[mona] configuring\n'
(
	cd "${MONA_SOURCE_DIR}"
	./configure --prefix="${MONA_SOURCE_DIR}/.local" \
		>"${EXTERNAL_DIR}/mona-configure.log" 2>&1
)

printf '[mona] building\n'
(
	cd "${MONA_SOURCE_DIR}"
	make -j"${MONA_JOBS:-$(sysctl -n hw.ncpu 2>/dev/null || nproc 2>/dev/null || echo 4)}" \
		>"${EXTERNAL_DIR}/mona-build.log" 2>&1
)

printf '[mona] ready: %s\n' "${MONA_SOURCE_DIR}/Front/mona"
printf '[mona] logs: %s %s\n' \
	"${EXTERNAL_DIR}/mona-configure.log" \
	"${EXTERNAL_DIR}/mona-build.log"
