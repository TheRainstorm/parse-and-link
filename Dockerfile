FROM python:slim

WORKDIR /parse-and-link
ADD requirements.txt /parse-and-link/requirements.txt
RUN rm -rf /etc/localtime \
&& ln -s /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
&& pip install --no-cache-dir -r requirements.txt

COPY . .

ARG PUID=1000
ARG PGID=1000
# create user
RUN groupadd -g $PGID mygroup && useradd -u $PUID -g mygroup -m -d /home/myuser -s /bin/bash myuser \
&& chown -R myuser:mygroup /parse-and-link

ENTRYPOINT [ "/parse-and-link/docker/entrypoint.sh" ]
