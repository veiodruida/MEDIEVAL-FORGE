# setup.sh
pip install -e ".[dev]" &&
python -m alembic upgrade head &&
cd frontend && npm install && npm run build && cd .. &&
cp -r frontend/dist/* backend/medieval_forge/static/ &&
python -m medieval-forge start
