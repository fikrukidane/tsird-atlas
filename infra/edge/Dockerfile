FROM nginx:alpine
COPY nginx.conf /etc/nginx/nginx.conf
RUN mkdir -p /var/log/tsird
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
