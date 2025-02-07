FROM python:3.9

WORKDIR /work

COPY pyproject.toml .
COPY version.txt .
COPY setup.py .
# Install only dependencies
RUN mkdir src
RUN pip install -e .[dev]

# Copy source last
COPY . .

ENV PATH=$PATH:/work
ENV PYTHONPATH=/work/src

CMD ["/bin/bash"]
