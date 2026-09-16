#!/usr/bin/env bash
set -euo pipefail

readonly WORK_ROOT="/work"
readonly PYTHON_ABI="${BPY_PYTHON_ABI:-cp311-cp311}"
readonly TARGET_PYTHON="/opt/python/${PYTHON_ABI}/bin/python"
readonly BASE_STAGE="${WORK_ROOT}/stage/base"
readonly SOURCE_DIR="${WORK_ROOT}/source/blender"
readonly RESULTS="${WORK_ROOT}/reports/pruning-results.tsv"
readonly REMOVED_FILES="${WORK_ROOT}/reports/pruned-files.tsv"

current_stage="${BASE_STAGE}"
candidate_number=0
candidate_path=""

mkdir -p "${WORK_ROOT}/reports/pruning-models" "${WORK_ROOT}/logs/pruning"
printf 'candidate\tresult\tbefore_bytes\tafter_bytes\tsaved_bytes\n' > "${RESULTS}"
printf 'candidate\tpath\tbytes\treason\n' > "${REMOVED_FILES}"

stage_bytes() {
  du --bytes --summarize "$1" | cut -f1
}

run_contract() {
  local stage="$1"
  local name="$2"
  local model_dir="${WORK_ROOT}/reports/pruning-models/${name}"

  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="${stage}" "${TARGET_PYTHON}" -c \
    'import bpy; print("IMPORT_OK", bpy.__file__, bpy.app.version_string)'
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="${stage}" "${TARGET_PYTHON}" \
    "${WORK_ROOT}/tests/verify_blend.py" write "${model_dir}"
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="${stage}" "${TARGET_PYTHON}" \
    "${WORK_ROOT}/tests/verify_blend.py" read "${model_dir}"
}

runtime_log_is_clean() {
  local log="$1"
  ! grep --extended-regexp --ignore-case --quiet \
    '(^Internal error:|^Error:|^Add-on not loaded:|Traceback|ModuleNotFoundError|ImportError|Segmentation fault|undefined symbol|cannot open shared object|Color management:.*(fail|error|missing|not found))' \
    "${log}"
}

record_removed_files() {
  local name="$1"
  local stage="$2"
  local output="$3"
  shift 3
  local relative_path target file relative bytes xtrace_was_enabled=false
  if [[ "$-" == *x* ]]; then
    xtrace_was_enabled=true
    set +x
  fi
  for relative_path in "$@"; do
    target="${stage}/${relative_path}"
    if [[ -d "${target}" ]]; then
      while IFS= read -r -d '' file; do
        relative="${file#"${stage}/"}"
        bytes="$(stat --dereference --format='%s' "${file}")"
        printf '%s\t%s\t%s\t%s\n' \
          "${name}" "${relative}" "${bytes}" 'not required by the tested export contract' \
          >> "${output}"
      done < <(find "${target}" \( -type f -o -type l \) -print0)
    elif [[ -e "${target}" || -L "${target}" ]]; then
      bytes="$(stat --dereference --format='%s' "${target}")"
      printf '%s\t%s\t%s\t%s\n' \
        "${name}" "${relative_path}" "${bytes}" 'not required by the tested export contract' \
      >> "${output}"
    fi
  done
  if [[ "${xtrace_was_enabled}" == true ]]; then
    set -x
  fi
}

new_candidate() {
  local name="$1"
  candidate_number=$((candidate_number + 1))
  candidate_path="${WORK_ROOT}/stage/prune-${candidate_number}-${name}"
  rm -rf -- "${candidate_path}"
  cp --archive --link -- "${current_stage}" "${candidate_path}"
}

record_candidate() {
  local name="$1"
  local result="$2"
  local before="$3"
  local after="$4"
  printf '%s\t%s\t%s\t%s\t%s\n' \
    "${name}" "${result}" "${before}" "${after}" "$((before - after))" >> "${RESULTS}"
}

try_remove() {
  local name="$1"
  shift
  local before candidate after log removal_manifest
  before="$(stage_bytes "${current_stage}")"
  new_candidate "${name}"
  candidate="${candidate_path}"
  log="${WORK_ROOT}/logs/pruning/${name}.log"
  removal_manifest="${WORK_ROOT}/logs/pruning/${name}-removed.tsv"
  : > "${removal_manifest}"
  record_removed_files "${name}" "${candidate}" "${removal_manifest}" "$@"
  for relative_path in "$@"; do
    rm -rf -- "${candidate}/${relative_path}"
  done
  after="$(stage_bytes "${candidate}")"

  if run_contract "${candidate}" "${name}" >"${log}" 2>&1 && \
      runtime_log_is_clean "${log}"; then
    cat "${removal_manifest}" >> "${REMOVED_FILES}"
    record_candidate "${name}" ACCEPTED "${before}" "${after}"
    if [[ "${current_stage}" != "${BASE_STAGE}" ]]; then
      rm -rf -- "${current_stage}"
    fi
    current_stage="${candidate}"
  else
    record_candidate "${name}" REJECTED "${before}" "${after}"
    rm -rf -- "${candidate}"
  fi
  rm -f -- "${removal_manifest}"
}

try_runtime_closure() {
  local name="runtime-elf-closure"
  local before candidate after log closure_report
  before="$(stage_bytes "${current_stage}")"
  new_candidate "${name}"
  candidate="${candidate_path}"
  log="${WORK_ROOT}/logs/pruning/${name}.log"
  closure_report="${WORK_ROOT}/reports/runtime-elf-closure.json"

  if "${TARGET_PYTHON}" "${WORK_ROOT}/scripts/prune_runtime_libs.py" \
      "${candidate}" "${closure_report}" >"${log}" 2>&1 && \
      run_contract "${candidate}" "${name}" >>"${log}" 2>&1 && \
      runtime_log_is_clean "${log}"; then
    after="$(stage_bytes "${candidate}")"
    record_candidate "${name}" ACCEPTED "${before}" "${after}"
    if [[ "${current_stage}" != "${BASE_STAGE}" ]]; then
      rm -rf -- "${current_stage}"
    fi
    current_stage="${candidate}"
  else
    after="$(stage_bytes "${candidate}")"
    record_candidate "${name}" REJECTED "${before}" "${after}"
    rm -rf -- "${candidate}"
  fi
}

try_remove_python_bytecode() {
  local name="generated-python-bytecode"
  local before candidate after log removal_manifest file relative bytes
  local xtrace_was_enabled=false
  before="$(stage_bytes "${current_stage}")"
  new_candidate "${name}"
  candidate="${candidate_path}"
  log="${WORK_ROOT}/logs/pruning/${name}.log"
  removal_manifest="${WORK_ROOT}/logs/pruning/${name}-removed.tsv"
  : > "${removal_manifest}"

  if [[ "$-" == *x* ]]; then
    xtrace_was_enabled=true
    set +x
  fi
  while IFS= read -r -d '' file; do
    relative="${file#"${candidate}/"}"
    bytes="$(stat --format='%s' "${file}")"
    printf '%s\t%s\t%s\t%s\n' \
      "${name}" "${relative}" "${bytes}" \
      'generated cache; Python source is retained' >> "${removal_manifest}"
    rm -f -- "${file}"
  done < <(find "${candidate}/bpy" -type f -name '*.pyc' -print0)
  find "${candidate}/bpy" -type d -name '__pycache__' -empty -delete
  if [[ "${xtrace_was_enabled}" == true ]]; then
    set -x
  fi
  after="$(stage_bytes "${candidate}")"

  if run_contract "${candidate}" "${name}" > "${log}" 2>&1 && \
      runtime_log_is_clean "${log}"; then
    cat "${removal_manifest}" >> "${REMOVED_FILES}"
    record_candidate "${name}" ACCEPTED "${before}" "${after}"
    if [[ "${current_stage}" != "${BASE_STAGE}" ]]; then
      rm -rf -- "${current_stage}"
    fi
    current_stage="${candidate}"
  else
    record_candidate "${name}" REJECTED "${before}" "${after}"
    rm -rf -- "${candidate}"
  fi
  rm -f -- "${removal_manifest}"
}

try_strip() {
  local name="strip-native-binaries"
  local before candidate after log file
  local xtrace_was_enabled=false
  before="$(stage_bytes "${current_stage}")"
  candidate_number=$((candidate_number + 1))
  candidate="${WORK_ROOT}/stage/prune-${candidate_number}-${name}"
  rm -rf -- "${candidate}"
  # Stripping mutates files, so this candidate must not share hard-links with
  # the last known-good stage.
  cp --archive -- "${current_stage}" "${candidate}"
  log="${WORK_ROOT}/logs/pruning/${name}.log"
  if [[ "$-" == *x* ]]; then
    xtrace_was_enabled=true
    set +x
  fi
  while IFS= read -r -d '' file; do
    if readelf --file-header "${file}" >/dev/null 2>&1; then
      strip --strip-unneeded -- "${file}"
    fi
  done < <(find "${candidate}/bpy" -type f -print0)
  if [[ "${xtrace_was_enabled}" == true ]]; then
    set -x
  fi
  after="$(stage_bytes "${candidate}")"

  if run_contract "${candidate}" "${name}" >"${log}" 2>&1 && \
      runtime_log_is_clean "${log}"; then
    record_candidate "${name}" ACCEPTED "${before}" "${after}"
    if [[ "${current_stage}" != "${BASE_STAGE}" ]]; then
      rm -rf -- "${current_stage}"
    fi
    current_stage="${candidate}"
  else
    record_candidate "${name}" REJECTED "${before}" "${after}"
    rm -rf -- "${candidate}"
  fi
}

# Each category is accepted only after a fresh import, writer process and reader
# process.  The order starts with the largest known build-installation leakage.
try_remove python-bundle "bpy/4.5/python"
try_runtime_closure
try_remove unused-core-addons \
  "bpy/4.5/scripts/addons_core/copy_global_transform.py" \
  "bpy/4.5/scripts/addons_core/hydra_storm" \
  "bpy/4.5/scripts/addons_core/node_wrangler" \
  "bpy/4.5/scripts/addons_core/rigify" \
  "bpy/4.5/scripts/addons_core/ui_translate" \
  "bpy/4.5/scripts/addons_core/viewport_vr_preview"
try_remove presets-and-templates \
  "bpy/4.5/scripts/presets" \
  "bpy/4.5/scripts/templates_osl" \
  "bpy/4.5/scripts/templates_py" \
  "bpy/4.5/scripts/templates_toml" \
  "bpy/4.5/scripts/freestyle" \
  "bpy/4.5/extensions"
try_remove ui-startup \
  "bpy/4.5/scripts/startup/bl_ui" \
  "bpy/4.5/scripts/startup/bl_app_templates_system"
try_remove remaining-startup "bpy/4.5/scripts/startup"
try_remove optional-script-modules \
  "bpy/4.5/scripts/modules/animsys_refactor.py" \
  "bpy/4.5/scripts/modules/bl_app_override" \
  "bpy/4.5/scripts/modules/bl_console_utils" \
  "bpy/4.5/scripts/modules/bl_i18n_utils" \
  "bpy/4.5/scripts/modules/bl_keymap_utils" \
  "bpy/4.5/scripts/modules/bl_previews_utils" \
  "bpy/4.5/scripts/modules/bl_rna_utils" \
  "bpy/4.5/scripts/modules/bl_text_utils" \
  "bpy/4.5/scripts/modules/bl_ui_utils" \
  "bpy/4.5/scripts/modules/blend_render_info.py" \
  "bpy/4.5/scripts/modules/bpy_extras" \
  "bpy/4.5/scripts/modules/console_python.py" \
  "bpy/4.5/scripts/modules/console_shell.py" \
  "bpy/4.5/scripts/modules/gpu_extras" \
  "bpy/4.5/scripts/modules/graphviz_export.py" \
  "bpy/4.5/scripts/modules/keyingsets_utils.py" \
  "bpy/4.5/scripts/modules/nodeitems_utils.py" \
  "bpy/4.5/scripts/modules/rna_info.py" \
  "bpy/4.5/scripts/modules/rna_keymap_ui.py" \
  "bpy/4.5/scripts/modules/rna_manual_reference.py" \
  "bpy/4.5/scripts/modules/rna_prop_ui.py" \
  "bpy/4.5/scripts/modules/rna_xml.py"
try_remove optional-assets \
  "bpy/4.5/datafiles/assets" \
  "bpy/4.5/datafiles/icons" \
  "bpy/4.5/datafiles/studiolights"
try_remove interface-fonts "bpy/4.5/datafiles/fonts"
try_remove color-management "bpy/4.5/datafiles/colormanagement"
try_remove_python_bytecode
try_strip

readonly MINIMAL_STAGE="${WORK_ROOT}/stage/minimal"
rm -rf -- "${MINIMAL_STAGE}"
cp --archive --link -- "${current_stage}" "${MINIMAL_STAGE}"
mkdir -p "${MINIMAL_STAGE}/bpy/licenses/third_party"
cp -- "${SOURCE_DIR}/release/text/copyright.txt" \
  "${MINIMAL_STAGE}/bpy/licenses/copyright.txt"
cp --archive -- "${SOURCE_DIR}/release/license/." \
  "${MINIMAL_STAGE}/bpy/licenses/third_party/"
# Defense in depth against stale setuptools output inherited from an earlier
# packaging run.  The wheel must be assembled only from the tested bpy tree.
rm -rf -- "${MINIMAL_STAGE}/build" "${MINIMAL_STAGE}/bpy.egg-info"
run_contract "${MINIMAL_STAGE}" final-minimal \
  >"${WORK_ROOT}/logs/pruning/final-minimal.log" 2>&1
runtime_log_is_clean "${WORK_ROOT}/logs/pruning/final-minimal.log"

mkdir -p \
  "${WORK_ROOT}/dist/minimal-raw" \
  "${WORK_ROOT}/dist/minimal-deflate9" \
  "${WORK_ROOT}/dist/minimal-zopfli" \
  "${WORK_ROOT}/dist/minimal"
SOURCE_DATE_EPOCH=1757335597 "${TARGET_PYTHON}" \
  "${SOURCE_DIR}/build_files/utils/make_bpy_wheel.py" \
  "${MINIMAL_STAGE}" --build-dir "${WORK_ROOT}/build/base" \
  --output-dir "${WORK_ROOT}/dist/minimal-raw"

wheels=("${WORK_ROOT}"/dist/minimal-raw/*.whl)
test "${#wheels[@]}" -eq 1
readonly RAW_WHEEL="${wheels[0]}"
readonly WHEEL_NAME="$(basename "${RAW_WHEEL}")"
readonly DEFLATE9_WHEEL="${WORK_ROOT}/dist/minimal-deflate9/${WHEEL_NAME}"
readonly ZOPFLI_WHEEL="${WORK_ROOT}/dist/minimal-zopfli/${WHEEL_NAME}"

"${TARGET_PYTHON}" "${WORK_ROOT}/scripts/repack_wheel.py" \
  "${RAW_WHEEL}" "${DEFLATE9_WHEEL}" "${WORK_ROOT}/reports/repack-deflate9.json" \
  --mode deflate9
"${TARGET_PYTHON}" "${WORK_ROOT}/scripts/repack_wheel.py" \
  "${RAW_WHEEL}" "${ZOPFLI_WHEEL}" "${WORK_ROOT}/reports/repack-zopfli.json" \
  --mode zopfli --iterations 15

smallest_wheel="${RAW_WHEEL}"
for candidate in "${DEFLATE9_WHEEL}" "${ZOPFLI_WHEEL}"; do
  if [[ "$(stat --format='%s' "${candidate}")" -lt \
        "$(stat --format='%s' "${smallest_wheel}")" ]]; then
    smallest_wheel="${candidate}"
  fi
done
cp -- "${smallest_wheel}" "${WORK_ROOT}/dist/minimal/${WHEEL_NAME}"
readonly WHEEL="${WORK_ROOT}/dist/minimal/${WHEEL_NAME}"

"${TARGET_PYTHON}" "${WORK_ROOT}/scripts/analyze_wheel.py" \
  "${WHEEL}" "${WORK_ROOT}/reports/minimal-wheel.json" \
  | tee "${WORK_ROOT}/reports/minimal-wheel.txt"
"${TARGET_PYTHON}" -m auditwheel show "${WHEEL}" \
  | tee "${WORK_ROOT}/reports/minimal-auditwheel-show.txt"
"${TARGET_PYTHON}" -c \
  'from email.parser import BytesParser; import sys, zipfile; z=zipfile.ZipFile(sys.argv[1]); p=next(n for n in z.namelist() if n.endswith(".dist-info/METADATA")); m=BytesParser().parsebytes(z.read(p)); assert not m.get_all("Requires-Dist", []), m.get_all("Requires-Dist")' \
  "${WHEEL}"

# Install exactly what notebook users receive.  NumPy 2.0.2 matches the main
# repository; bpy itself intentionally has no NumPy integration in this build.
readonly CLEAN_VENV="${WORK_ROOT}/venv/minimal"
"${TARGET_PYTHON}" -m venv "${CLEAN_VENV}"
"${CLEAN_VENV}/bin/python" -m pip install --disable-pip-version-check \
  'numpy==2.0.2'
"${CLEAN_VENV}/bin/python" -m pip install --disable-pip-version-check \
  --no-deps "${WHEEL}"
"${CLEAN_VENV}/bin/python" -c \
  'import numpy; assert numpy.__version__ == "2.0.2"; import bpy; print("CLEAN_IMPORT_OK", bpy.__file__, bpy.app.version_string, numpy.__version__)'
"${CLEAN_VENV}/bin/python" "${WORK_ROOT}/tests/verify_blend.py" \
  write "${WORK_ROOT}/reports/clean-wheel-models"
"${CLEAN_VENV}/bin/python" "${WORK_ROOT}/tests/verify_blend.py" \
  read "${WORK_ROOT}/reports/clean-wheel-models"
"${CLEAN_VENV}/bin/python" -m pip freeze \
  > "${WORK_ROOT}/reports/minimal-clean-environment.txt"
