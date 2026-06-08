SWAGGER_CONFIG = {
    "headers": [],
    "specs": [
        {
            "endpoint": 'apispec_v1',
            "route": '/api/v1/apispec.json',
            "rule_filter": lambda rule: rule.endpoint.startswith('api_v1'),
            "model_filter": lambda model: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/apidocs/",
    "title": "TechInsights Developer REST API Documentation",
    "description": "Production-grade versioned RESTful endpoints for the TechInsights blogging platform. Supports secure JWT Bearer authorization, pagination, nested comments, followers, and media uploads.",
    "version": "1.0.0",
}

SWAGGER_TEMPLATE = {
    "swagger": "2.0",
    "info": {
        "title": "TechInsights Developer API",
        "description": "Interactive developer documentation for the TechInsights Flask Blogging Platform REST API. Built on Flask, Gunicorn, PostgreSQL, and Redis.",
        "contact": {
            "name": "Surendra Mahla",
            "email": "surendramahla087@gmail.com"
        },
        "version": "1.0.0"
    },
    "basePath": "/",
    "schemes": [
        "http",
        "https"
    ],
    "securityDefinitions": {
        "ApiKeyAuth": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
            "description": "JWT Access Token. Input format: `Bearer <JWT_ACCESS_TOKEN>`"
        }
    },
    "security": [
        {
            "ApiKeyAuth": []
        }
    ]
}
