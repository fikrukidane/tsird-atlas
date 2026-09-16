FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy all web application files
COPY index.html /usr/share/nginx/html/
COPY src/ /usr/share/nginx/html/src/
COPY js/ /usr/share/nginx/html/js/
COPY css/ /usr/share/nginx/html/css/
COPY data/ /usr/share/nginx/html/data/
COPY drought/ /usr/share/nginx/html/drought/

EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
