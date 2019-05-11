FROM python:3.5

COPY requirements.txt /code/requirements.txt
RUN pip install  --no-cache-dir -r /code/requirements.txt

COPY main.py /code/
COPY lootcrate.py /code/
COPY phrases.py /code/
COPY token.txt /code/

CMD python /code/main.py
