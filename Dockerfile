FROM alpine:latest

RUN apk add --update --no-cache htop
RUN apk add --update --no-cache python3 py3-pip && ln -sf python3 /usr/bin/python

RUN pip install --upgrade pip && \
    pip install --no-cache-dir influxdb

EXPOSE 2947

COPY influx-script/influx-connector.py /opt/influx-connector.py
RUN ["chmod", "a+x", "/opt/influx-connector.py"]

#ENTRYPOINT ["python", "/opt/influx-connector.py"]
ENTRYPOINT [ "htop" ]