#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_DIR="${PROJECT_ROOT}/.external/VAL"
BUILD_DIR="${PROJECT_ROOT}/.external/val-build"
REVISION="3c7a1f330bdab0ba28a4762bb45c3f06c27fb6d4"

if [[ ! -d "${SOURCE_DIR}/.git" ]]; then
	mkdir -p "$(dirname "${SOURCE_DIR}")"
	git clone https://github.com/KCL-Planning/VAL "${SOURCE_DIR}"
fi
if [[ -n "$(git -C "${SOURCE_DIR}" status --porcelain)" ]]; then
	printf 'VAL source contains local changes: %s\n' "${SOURCE_DIR}" >&2
	exit 1
fi
if [[ "$(git -C "${SOURCE_DIR}" rev-parse HEAD)" != "${REVISION}" ]]; then
	git -C "${SOURCE_DIR}" fetch origin "${REVISION}"
	git -C "${SOURCE_DIR}" checkout --detach "${REVISION}"
fi

cmake -S "${SOURCE_DIR}" -B "${BUILD_DIR}" \
	-DCMAKE_BUILD_TYPE=Release -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
	-DCMAKE_CXX_FLAGS="-DYYMAXDEPTH=1000000"
cmake --build "${BUILD_DIR}" --target Validate --parallel "${VAL_BUILD_JOBS:-4}"
printf '\nSet VAL_VALIDATE_BIN to %s\n' "${BUILD_DIR}/bin/Validate"
