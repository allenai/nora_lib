FROM python:3.9

WORKDIR /work

COPY pyproject.toml .
COPY setup.py .
RUN pip install -e .[dev]

# Do this last for :sanic:
COPY . .

ENV PATH $PATH:/work
ENV PYTHONPATH /work

ENV PYTHONPATH /work

CMD ["/bin/bash"]
