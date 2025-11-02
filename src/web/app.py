"""
Flask web application for NYC Events Scraper
"""
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_cors import CORS
from sqlalchemy import desc, and_, or_
from sqlalchemy.orm import sessionmaker, joinedload
from datetime import datetime, timedelta
import os
from src.web.models import CleanEvent, Venue, engine, Base
from src.config import Config
from src.logger import get_logger

# Initialize Flask app
app = Flask(__name__, 
            template_folder='../../templates',
            static_folder='../../static')
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
        per_page = min(request.args.get('per_page', 100, type=int), 100)
        venue_filter = request.args.get('venue', '')
        date_shortcut = request.args.get('date_shortcut', '')  # today, this_weekend, next_weekend
        date_start_param = request.args.get('date_start', '')  # YYYY-MM-DD
        date_end_param = request.args.get('date_end', '')  # YYYY-MM-DD
        max_time = request.args.get('max_time', type=int)
        modes = request.args.get('modes', '', type=str)
        
        # Base query
        query = db.query(CleanEvent).options(joinedload(CleanEvent.venue_ref))

        # Date filtering
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        date_from = today_start
        date_to = None

        # Apply shortcut filters
        if date_shortcut == 'today':
            date_from = today_start
            date_to = today_start + timedelta(days=1)
        elif date_shortcut in ('this_weekend', 'next_weekend'):
            # Find the upcoming Friday relative to today
            # Monday is 0, Sunday is 6; Friday is 5
            weekday = today_start.weekday()
            days_until_friday = (4 - weekday) % 7  # 4 represents Friday (0-based: Mon=0)
            # Correct Friday index: In Python, Monday=0, Friday=4
            # Recompute with correct mapping
            days_until_friday = (4 - weekday) % 7
            first_friday = today_start + timedelta(days=days_until_friday)
            if date_shortcut == 'next_weekend':
                first_friday = first_friday + timedelta(days=7)
            # Weekend window: Friday 00:00 to Monday 00:00
            date_from = first_friday
            date_to = first_friday + timedelta(days=3)

        # Apply explicit date range if provided (overrides shortcut)
        # Single date: only date_start provided -> filter that day
        # Range: both provided -> inclusive of both days
        start_dt = None
        end_dt = None
        if date_start_param:
            try:
                start_dt = datetime.strptime(date_start_param, '%Y-%m-%d')
            except ValueError:
                start_dt = None
        if date_end_param:
            try:
                end_dt = datetime.strptime(date_end_param, '%Y-%m-%d')
            except ValueError:
                end_dt = None

        if start_dt and end_dt:
            # Inclusive range [start_dt, end_dt]
            date_from = start_dt
            date_to = end_dt + timedelta(days=1)
        elif start_dt and not end_dt:
            # Single day selection
            date_from = start_dt
            date_to = start_dt + timedelta(days=1)

        # Default: from today onward
        if date_from:
            query = query.filter(CleanEvent.start_time >= date_from)
        if date_to:
            query = query.filter(CleanEvent.start_time < date_to)

        # Order by start time
        query = query.order_by(CleanEvent.start_time)
        
        # Apply venue filter if provided (use display_venue for filtering)
        if venue_filter:
            query = query.filter(CleanEvent.display_venue == venue_filter)
        
        # Apply distance/time filter if provided
        if max_time and modes:
            mode_list = [m.strip().lower() for m in modes.split(',') if m.strip()]
            if mode_list:
                conditions = []
                if 'walk' in mode_list or 'walking' in mode_list:
                    conditions.append(CleanEvent.venue_ref.has(Venue.walking_time_min <= max_time))
                if 'subway' in mode_list:
                    conditions.append(CleanEvent.venue_ref.has(Venue.subway_time_min <= max_time))
                if 'drive' in mode_list or 'driving' in mode_list:
                    conditions.append(CleanEvent.venue_ref.has(Venue.driving_time_min <= max_time))
                
                if conditions:
                    # Join with OR logic - event matches if ANY mode meets the time requirement
                    query = query.filter(or_(*conditions))
        
        # Get total events count before pagination
        total_events = query.count()
        
        # Pagination
        events = query.offset((page - 1) * per_page).limit(per_page).all()
        
        # Get all unique display venues for the filter dropdown (excluding None/null venues)
        all_venues = db.query(CleanEvent.display_venue).filter(
            CleanEvent.display_venue.isnot(None),
            CleanEvent.display_venue != ''
        ).distinct().order_by(CleanEvent.display_venue).all()
        venues = [v[0] for v in all_venues]
        
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
                             has_next=has_next,
                             venues=venues,
                             venue_filter=venue_filter,
                             date_shortcut=date_shortcut,
                             date_start=date_start_param,
                             date_end=date_end_param,
                             max_time=max_time if max_time else 60,
                             modes=modes if modes else 'walk,subway,drive')
    
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
        max_time = request.args.get('max_time', type=int)
        modes = request.args.get('modes', '', type=str)
        response_format = request.args.get('format', 'json', type=str)
        
        # Build query
        query = db.query(CleanEvent).options(joinedload(CleanEvent.venue_ref))
        
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
        
        # Apply distance/time filter if provided
        if max_time and modes:
            mode_list = [m.strip().lower() for m in modes.split(',') if m.strip()]
            if mode_list:
                conditions = []
                if 'walk' in mode_list or 'walking' in mode_list:
                    conditions.append(CleanEvent.venue_ref.has(Venue.walking_time_min <= max_time))
                if 'subway' in mode_list:
                    conditions.append(CleanEvent.venue_ref.has(Venue.subway_time_min <= max_time))
                if 'drive' in mode_list or 'driving' in mode_list:
                    conditions.append(CleanEvent.venue_ref.has(Venue.driving_time_min <= max_time))
                
                if conditions:
                    # Join with OR logic - event matches if ANY mode meets the time requirement
                    query = query.filter(or_(*conditions))
        
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
                'venue_id': event.venue_id,
                'venue_name': event.venue_ref.name if event.venue_ref else None,
                'venue_location_text': event.venue_ref.location_text if event.venue_ref else None,
                'venue_latitude': event.venue_ref.latitude if event.venue_ref else None,
                'venue_longitude': event.venue_ref.longitude if event.venue_ref else None,
                'haversine_distance_miles': event.venue_ref.haversine_distance_miles if event.venue_ref else None,
                'driving_time_min': event.venue_ref.driving_time_min if event.venue_ref else None,
                'walking_time_min': event.venue_ref.walking_time_min if event.venue_ref else None,
                'subway_time_min': event.venue_ref.subway_time_min if event.venue_ref else None,
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
                'date_to': date_to,
                'max_time': max_time,
                'modes': modes
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


# Run with: python run_app.py from the root directory
