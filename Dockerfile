FROM balenalib/raspberrypi4-64-python:latest

ENV DBUS_SYSTEM_BUS_ADDRESS=unix:path=/host/run/dbus/system_bus_socket
ENV UDEV=1

RUN install_packages \
  build-essential \
  bluez \
  python-dbus \
  python-dev \
  libglib2.0-dev \
  htop

RUN pip install influxdb gatt --no-cache-dir

CMD sleep 3600

COPY influx-script/influx-connector.py /opt/influx-connector.py
RUN ["chmod", "a+x", "/opt/influx-connector.py"]

#ENTRYPOINT ["python", "/opt/influx-connector.py"]
ENTRYPOINT [ "htop" ]