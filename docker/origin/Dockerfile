FROM python:3.9-slim-bookworm

# Stands in for an edge or a canary. Stdlib only, so there is nothing to install.
COPY docker/origin/server.py /usr/local/bin/origin_server.py
COPY docker/conf/myobject.edgemanage /srv/myobject.edgemanage

EXPOSE 80

CMD ["python3", "-u", "/usr/local/bin/origin_server.py"]
