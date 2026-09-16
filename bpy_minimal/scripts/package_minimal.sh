#!/usr/bin/env bash
set -euo pipefail

readonly WORK_ROOT="/work"
readonly TARGET_PYTHON="/opt/python/cp311-cp311/bin/python"
readonly BASE_STAGE="${WORK_ROOT}/stage/base"
readonly SOURCE_DIR="${WORK_ROOT}/source/blender"
readonly RESULTS="${WORK_ROOT}/reports/pruning-results.tsv"

current_stage="${BASE_STAGE}"
candidate_number=0
candidate_path=""

mkdir -p "${WORK_ROOT}/reports/pruning-models" "${WORK_ROOT}/logs/pruning"
printf 'candidate\tresult\tbefore_bytes\tafter_bytes\tsaved_bytes\n' > "${RESULTS}"

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
  local before candidate after log
  before="$(stage_bytes "${current_stage}")"
  new_candidate "${name}"
  candidate="${candidate_path}"
  log="${WORK_ROOT}/logs/pruning/${name}.log"
  for relative_path in "$@"; do
    rm -rf -- "${candidate}/${relative_path}"
  done
  after="$(stage_bytes "${candidate}")"

  if run_contract "${candidate}" "${name}" >"${log}" 2>&1; then
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
      run_contract "${candidate}" "${name}" >>"${log}" 2>&1; then
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

try_strip() {
  local name="strip-native-binaries"
  local before candidate after log
  before="$(stage_bytes "${current_stage}")"
  candidate_number=$((candidate_number + 1))
  candidate="${WORK_ROOT}/stage/prune-${candidate_number}-${name}"
  rm -rf -- "${candidate}"
  # Stripping mutates files, so this candidate must not share hard-links with
  # the last known-good stage.
  cp --archive -- "${current_stage}" "${candidate}"
  log="${WORK_ROOT}/logs/pruning/${name}.log"
  find "${candidate}/bpy" -type f -name '*.so*' -exec strip --strip-unneeded -- {} +
  after="$(stage_bytes "${candidate}")"

  if run_contract "${candidate}" "${name}" >"${log}" 2>&1; then
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
try_remove addons-core "bpy/4.5/scripts/addons_core"
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
try_strip

readonly MINIMAL_STAGE="${WORK_ROOT}/stage/minimal"
rm -rf -- "${MINIMAL_STAGE}"
cp --archive --link -- "${current_stage}" "${MINIMAL_STAGE}"
run_contract "${MINIMAL_STAGE}" final-minimal \
  >"${WORK_ROOT}/logs/pruning/final-minimal.log" 2>&1

mkdir -p "${WORK_ROOT}/dist/minimal"
SOURCE_DATE_EPOCH=1757335597 "${TARGET_PYTHON}" \
  "${SOURCE_DIR}/build_files/utils/make_bpy_wheel.py" \
  "${MINIMAL_STAGE}" --build-dir "${WORK_ROOT}/build/base" \
  --output-dir "${WORK_ROOT}/dist/minimal"

wheels=("${WORK_ROOT}"/dist/minimal/*.whl)
test "${#wheels[@]}" -eq 1
readonly WHEEL="${wheels[0]}"

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
