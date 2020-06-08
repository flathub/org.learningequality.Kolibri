#!/bin/bash -xe

SHARED_LOCALES_DIR=$1
shift 1

for SOURCE_DIR in $@; do
    if [ ! -d ${SOURCE_DIR} ]; then
        echo "Source directory '${SOURCE_DIR}' does not exist"
        exit 1
    fi

    pushd "${SOURCE_DIR}"

    for LOCALE_NAME in *; do
        SOURCE_DIR_FULL=$(readlink -e "${LOCALE_NAME}")
        TARGET_DIR_FULL=$(readlink -m "${SHARED_LOCALES_DIR}/${LOCALE_NAME}/${SOURCE_DIR_FULL}")

        if [ -d "${TARGET_DIR_FULL}" ]; then
            echo "Target directory '${TARGET_DIR_FULL}' already exists"
            exit 1
        fi

        if [ -d "${SOURCE_DIR_FULL}" ]; then
            install -d "${TARGET_DIR_FULL}"
            rm -rf "${TARGET_DIR_FULL}"
            mv "${SOURCE_DIR_FULL}" "${TARGET_DIR_FULL}"
            ln -s "${TARGET_DIR_FULL}" "${SOURCE_DIR_FULL}"
        fi
    done

    popd
done

