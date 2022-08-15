FROM python:3.8-slim-buster
WORKDIR /app
COPY requirements.txt requirements.txt
COPY . .
RUN pip3 install jaeger-client
RUN pip3 install flask-opentracing
RUN pip3 install -r requirements.txt
ENV FLASK_APP=app.py
ENV FLASK_RUN_PORT=9099
# COPY . .
# CMD [ "python3", "app.py"]

