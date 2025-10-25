"""
Flask web application for NYC Events Scraper
"""
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_cors import CORS
from sqlalchemy import desc, and_, or_
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
import os
from models import CleanEvent, engine, Base
from config import Config
from logger import get_logger

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Enable CORS for API endpoints
CORS(app, origins=['*'])

# Database session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
logger = get_logger('flask_app')


def get_db_session():
    """Get database session"""
    return SessionLocal()


@app.route('/')
def index():
    """Home page - display events"""
    try:
        db = get_db_session()
        
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        # Build query - get all events ordered by start time
        query = db.query(CleanEvent).order_by(CleanEvent.start_time)
        
        # Pagination
        events = query.offset((page - 1) * per_page).limit(per_page).all()
        total_events = query.count()
        
        db.close()
        
        # Calculate pagination info
        total_pages = (total_events + per_page - 1) // per_page
        has_prev = page > 1
        has_next = page < total_pages
        
        return render_template('index.html',
                             events=events,
                             page=page,
                             per_page=per_page,
                             total_pages=total_pages,
                             has_prev=has_prev,
                             has_next=has_next)
    
    except Exception as e:
        logger.error(f"Error in index route: {e}")
        db.close()
        return render_template('error.html', error_message=str(e)), 500


@app.route('/event/<int:event_id>')
def event_detail(event_id):
    """Event detail page"""
    try:
        db = get_db_session()
        event = db.query(CleanEvent).filter(CleanEvent.id == event_id).first()
        db.close()
        
        if not event:
            return render_template('error.html', error_message="Event not found"), 404
        
        return render_template('event_detail.html', event=event)
    
    except Exception as e:
        logger.error(f"Error in event_detail route: {e}")
        db.close()
        return render_template('error.html', error_message=str(e)), 500


@app.route('/api/events')
def api_events():
    """JSON API endpoint for events with filtering and pagination
    
    Query Parameters:
    - page: Page number (default: 1)
    - per_page: Events per page (default: 20, max: 100)
    - search: Search in title and description
    - venue: Filter by venue name
    - category: Filter by category
    - date_from: Filter events from this date (YYYY-MM-DD)
    - date_to: Filter events until this date (YYYY-MM-DD)
    - format: Response format ('json' or 'csv')
    """
    try:
        db = get_db_session()
        
        # Get query parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)  # Max 100 per page
        search = request.args.get('search', '', type=str)
        venue = request.args.get('venue', '', type=str)
        category = request.args.get('category', '', type=str)
        date_from = request.args.get('date_from', '', type=str)
        date_to = request.args.get('date_to', '', type=str)
        response_format = request.args.get('format', 'json', type=str)
        
        # Build query
        query = db.query(CleanEvent)
        
        # Apply filters
        if search:
            query = query.filter(
                or_(
                    CleanEvent.title.ilike(f'%{search}%'),
                    CleanEvent.description.ilike(f'%{search}%')
                )
            )
        
        if venue:
            query = query.filter(CleanEvent.venue.ilike(f'%{venue}%'))
        
        if category:
            query = query.filter(CleanEvent.category.ilike(f'%{category}%'))
        
        if date_from:
            try:
                date_from_dt = datetime.strptime(date_from, '%Y-%m-%d')
                query = query.filter(CleanEvent.start_time >= date_from_dt)
            except ValueError:
                pass
        
        if date_to:
            try:
                date_to_dt = datetime.strptime(date_to, '%Y-%m-%d')
                date_to_dt += timedelta(days=1)
                query = query.filter(CleanEvent.start_time < date_to_dt)
            except ValueError:
                pass
        
        # Order by start time
        query = query.order_by(CleanEvent.start_time)
        
        # Pagination
        events = query.offset((page - 1) * per_page).limit(per_page).all()
        total_events = query.count()
        
        db.close()
        
        # Convert events to dictionaries
        events_data = []
        for event in events:
            event_dict = {
                'id': event.id,
                'title': event.title,
                'description': event.description,
                'start_time': event.start_time.isoformat() if event.start_time else None,
                'end_time': event.end_time.isoformat() if event.end_time else None,
                'location': event.location,
                'venue': event.venue,
                'price_range': event.price_range,
                'category': event.category,
                'url': event.url,
                'image_url': event.image_url,
                'source': event.source,
                'source_urls': event.source_urls,
                'created_at': event.created_at.isoformat() if event.created_at else None,
                'updated_at': event.updated_at.isoformat() if event.updated_at else None
            }
            events_data.append(event_dict)
        
        # Handle CSV format
        if response_format.lower() == 'csv':
            from flask import Response
            import csv
            import io
            
            output = io.StringIO()
            if events_data:
                writer = csv.DictWriter(output, fieldnames=events_data[0].keys())
                writer.writeheader()
                writer.writerows(events_data)
            
            return Response(
                output.getvalue(),
                mimetype='text/csv',
                headers={'Content-Disposition': 'attachment; filename=nyc_events.csv'}
            )
        
        # Default JSON response
        response = {
            'events': events_data,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_events': total_events,
                'total_pages': (total_events + per_page - 1) // per_page
            },
            'filters': {
                'search': search,
                'venue': venue,
                'category': category,
                'date_from': date_from,
                'date_to': date_to
            }
        }
        
        return jsonify(response)
    
    except Exception as e:
        logger.error(f"Error in api_events route: {e}")
        db.close()
        return jsonify({'error': str(e)}), 500


@app.route('/api/event/<int:event_id>')
def api_event_detail(event_id):
    """JSON API endpoint for single event"""
    try:
        db = get_db_session()
        event = db.query(CleanEvent).filter(CleanEvent.id == event_id).first()
        db.close()
        
        if not event:
            return jsonify({'error': 'Event not found'}), 404
        
        event_dict = {
            'id': event.id,
            'title': event.title,
            'description': event.description,
            'start_time': event.start_time.isoformat() if event.start_time else None,
            'end_time': event.end_time.isoformat() if event.end_time else None,
            'location': event.location,
            'venue': event.venue,
            'price_range': event.price_range,
            'category': event.category,
            'url': event.url,
            'image_url': event.image_url,
            'source': event.source,
            'source_urls': event.source_urls,
            'created_at': event.created_at.isoformat() if event.created_at else None,
            'updated_at': event.updated_at.isoformat() if event.updated_at else None
        }
        
        return jsonify(event_dict)
    
    except Exception as e:
        logger.error(f"Error in api_event_detail route: {e}")
        db.close()
        return jsonify({'error': str(e)}), 500


@app.route('/api/docs')
def api_docs():
    """API documentation endpoint"""
    docs = {
        'title': 'NYC Events API',
        'version': '1.0',
        'description': 'RESTful API for NYC Events data',
        'base_url': request.base_url.replace('/api/docs', ''),
        'endpoints': {
            '/api/events': {
                'method': 'GET',
                'description': 'Get paginated list of events with filtering',
                'parameters': {
                    'page': 'Page number (default: 1)',
                    'per_page': 'Events per page (default: 20, max: 100)',
                    'search': 'Search in title and description',
                    'venue': 'Filter by venue name',
                    'category': 'Filter by category',
                    'date_from': 'Filter events from this date (YYYY-MM-DD)',
                    'date_to': 'Filter events until this date (YYYY-MM-DD)',
                    'format': 'Response format (json or csv)'
                },
                'example': '/api/events?search=music&venue=Kings%20Theatre&per_page=10'
            },
            '/api/event/<id>': {
                'method': 'GET',
                'description': 'Get single event by ID',
                'parameters': {
                    'id': 'Event ID (integer)'
                },
                'example': '/api/event/158'
            },
            '/api/docs': {
                'method': 'GET',
                'description': 'API documentation (this endpoint)'
            },
            '/health': {
                'method': 'GET',
                'description': 'Health check endpoint'
            }
        },
        'response_format': {
            'events': [
                {
                    'id': 'integer',
                    'title': 'string',
                    'description': 'string',
                    'start_time': 'ISO datetime string',
                    'end_time': 'ISO datetime string',
                    'location': 'string',
                    'venue': 'string',
                    'price_range': 'string',
                    'category': 'string',
                    'url': 'string',
                    'image_url': 'string',
                    'source': 'string',
                    'source_urls': 'array of strings',
                    'created_at': 'ISO datetime string',
                    'updated_at': 'ISO datetime string'
                }
            ],
            'pagination': {
                'page': 'integer',
                'per_page': 'integer',
                'total_events': 'integer',
                'total_pages': 'integer'
            },
            'filters': {
                'search': 'string',
                'venue': 'string',
                'category': 'string',
                'date_from': 'string',
                'date_to': 'string'
            }
        }
    }
    return jsonify(docs)


@app.route('/health')
def health_check():
    """Health check endpoint"""
    try:
        db = get_db_session()
        # Test database connection
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        db.close()
        return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()})
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500


@app.errorhandler(404)
def not_found(error):
    """404 error handler"""
    return render_template('error.html', error_message="Page not found"), 404


@app.errorhandler(500)
def internal_error(error):
    """500 error handler"""
    logger.error(f"Internal server error: {error}")
    return render_template('error.html', error_message="Internal server error"), 500


if __name__ == '__main__':
    # Create tables if they don't exist
    Base.metadata.create_all(bind=engine)
    
    # Run the app
    app.run(debug=True, host='0.0.0.0', port=5000)
