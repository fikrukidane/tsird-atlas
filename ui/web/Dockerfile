FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html /usr/share/nginx/html/index.html
COPY css/ /usr/share/nginx/html/css/
COPY src/ /usr/share/nginx/html/src/
COPY data/ /usr/share/nginx/html/data/
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
