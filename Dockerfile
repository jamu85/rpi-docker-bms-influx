FROM python:3.8

RUN apt-get update && apt-get install -y --no-install-recommends \
  bluez-tools \
  bluez \
  bluetooth \
  build-essential \
  libdbus-glib-1-dev \
  libgirepository1.0-dev \
  pkg-config \
  libcairo2-dev \
  python3-dev \
  libgirepository1.0-dev \
  && rm -rf /var/lib/apt/lists/*

RUN pip3 install \
  gatt \
  influxdb_client \
  dbus-python \
  gobject \
  PyGObject


COPY influx-script/influx-connector.py /opt/influx-connector.py
RUN ["chmod", "a+x", "/opt/influx-connector.py"]

COPY docker_entrypoint.sh /opt/docker_entrypoint.sh
RUN ["chmod", "a+x", "/opt/docker_entrypoint.sh"]

#ENTRYPOINT ["python", "/opt/influx-connector.py"]
ENTRYPOINT [ "/opt/docker_entrypoint.sh" ]
