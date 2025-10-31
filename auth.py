"""
Authentication routes for Perfect AI Meeting Analyzer
Login, signup, logout functionality
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User, RecordingSession
from datetime import datetime
import re

auth_bp = Blueprint('auth', __name__)

def is_valid_email(email):
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def is_valid_password(password):
    """Validate password strength."""
    if len(password) < 6:
        return False, "Password must be at least 6 characters long"
    if not re.search(r'[A-Za-z]', password):
        return False, "Password must contain at least one letter"
    if not re.search(r'[0-9]', password):
        return False, "Password must contain at least one number"
    return True, "Valid password"

@auth_bp.route('/login')
def login_page():
    """Show login page."""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    return render_template('auth/login.html')

@auth_bp.route('/signup')
def signup_page():
    """Show signup page."""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    return render_template('auth/signup.html')

@auth_bp.route('/login', methods=['POST'])
def login():
    """Handle login form submission."""
    try:
        data = request.get_json() if request.is_json else request.form
        username = data.get('username', '').strip()
        password = data.get('password', '')
        remember = data.get('remember', False)
        
        if not username or not password:
            error = 'Username and password are required'
            if request.is_json:
                return jsonify({'success': False, 'error': error})
            flash(error, 'error')
            return redirect(url_for('auth.login_page'))
        
        # Find user by username or email
        user = User.query.filter(
            (User.username == username) | (User.email == username)
        ).first()
        
        if user and user.check_password(password) and user.is_active:
            # Update last login
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            # Log in user
            login_user(user, remember=remember)
            
            if request.is_json:
                return jsonify({
                    'success': True,
                    'message': 'Login successful',
                    'user': user.to_dict(),
                    'redirect': url_for('index')
                })
            
            flash(f'Welcome back, {user.full_name or user.username}!', 'success')
            return redirect(url_for('index'))
        else:
            error = 'Invalid username/email or password'
            if request.is_json:
                return jsonify({'success': False, 'error': error})
            flash(error, 'error')
            return redirect(url_for('auth.login_page'))
            
    except Exception as e:
        error = 'An error occurred during login'
        print(f"Login error: {e}")
        if request.is_json:
            return jsonify({'success': False, 'error': error})
        flash(error, 'error')
        return redirect(url_for('auth.login_page'))

@auth_bp.route('/signup', methods=['POST'])
def signup():
    """Handle signup form submission."""
    try:
        data = request.get_json() if request.is_json else request.form
        username = data.get('username', '').strip()
        email = data.get('email', '').strip().lower()
        full_name = data.get('full_name', '').strip()
        password = data.get('password', '')
        confirm_password = data.get('confirm_password', '')
        
        # Validation
        errors = []
        
        if not username or len(username) < 3:
            errors.append('Username must be at least 3 characters long')
        elif not re.match(r'^[a-zA-Z0-9_]+$', username):
            errors.append('Username can only contain letters, numbers, and underscores')
        
        if not email or not is_valid_email(email):
            errors.append('Please enter a valid email address')
        
        if not full_name:
            errors.append('Full name is required')
        
        if not password:
            errors.append('Password is required')
        else:
            is_valid, msg = is_valid_password(password)
            if not is_valid:
                errors.append(msg)
        
        if password != confirm_password:
            errors.append('Passwords do not match')
        
        # Check if user already exists
        if User.query.filter_by(username=username).first():
            errors.append('Username already exists')
        
        if User.query.filter_by(email=email).first():
            errors.append('Email already registered')
        
        if errors:
            error_msg = '; '.join(errors)
            if request.is_json:
                return jsonify({'success': False, 'error': error_msg})
            flash(error_msg, 'error')
            return redirect(url_for('auth.signup_page'))
        
        # Create new user
        user = User(
            username=username,
            email=email,
            full_name=full_name
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        # Log in the new user
        login_user(user)
        
        if request.is_json:
            return jsonify({
                'success': True,
                'message': 'Account created successfully',
                'user': user.to_dict(),
                'redirect': url_for('index')
            })
        
        flash(f'Welcome to Perfect AI, {user.full_name}!', 'success')
        return redirect(url_for('index'))
        
    except Exception as e:
        error = 'An error occurred during signup'
        print(f"Signup error: {e}")
        if request.is_json:
            return jsonify({'success': False, 'error': error})
        flash(error, 'error')
        return redirect(url_for('auth.signup_page'))

@auth_bp.route('/logout')
@login_required
def logout():
    """Handle user logout."""
    username = current_user.username
    logout_user()
    flash(f'Goodbye, {username}!', 'info')
    return redirect(url_for('auth.login_page'))

@auth_bp.route('/profile')
@login_required
def profile():
    """Show user profile page."""
    # Get user statistics
    total_sessions = RecordingSession.query.filter_by(user_id=current_user.id).count()
    active_sessions = RecordingSession.query.filter_by(
        user_id=current_user.id, 
        is_active=True
    ).count()
    
    return render_template('auth/profile.html', 
                         user=current_user,
                         total_sessions=total_sessions,
                         active_sessions=active_sessions)

@auth_bp.route('/api/user')
@login_required
def get_user_info():
    """Get current user information."""
    return jsonify({
        'success': True,
        'user': current_user.to_dict()
    })