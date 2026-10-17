#!/bin/bash
set -euo pipefail
python3 -m pip install --user 'scipy>=1.10' -q
python3 -c "import scipy; print('scipy', scipy.__version__)"
