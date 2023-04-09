FROM python:3.10-alpine

WORKDIR /app

ADD requirements.txt /app

RUN pip install --upgrade --no-cache-dir \
     -r /app/requirements.txt

ADD ./trans_rss /app/trans_rss

CMD ["uvicorn", "trans_rss:app", "--host", "0.0.0.0", "--port", "80"]

