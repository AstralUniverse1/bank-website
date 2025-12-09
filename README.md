
A simple bank website built with Flask (backend) and HTML/JS frontend.
Uses SQLite for data storage.


- backend/ – Flask application
- frontend/ – HTML, CSS, JS files for the UI
- Dockerfile – containerizes the app


The application is containerized using Docker. To run locally:

1. Build the Docker image:
   docker build -t bank-app .

2. Run the container:
   docker run -p 5000:5000 bank-app

3. Open your browser at http://127.0.0.1:5000  
