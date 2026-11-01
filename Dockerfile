FROM python:3.12-slim
WORKDIR /workspace
COPY . /workspace
RUN make check
CMD ["python3", "scripts/validate_packs.py"]
