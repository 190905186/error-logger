import streamlit as st
import sqlite3
import pandas as pd
import json
import sys
import platform
from datetime import datetime
from pathlib import Path

# Page configuration
st.set_page_config(
    page_title="Error Logger",
    page_icon="🐛",
    layout="wide"
)

# Database initialization
DB_PATH = "error_logger.db"

def init_db():
    """Initialize the database with required tables"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Environments table
    c.execute('''
        CREATE TABLE IF NOT EXISTS environments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            python_version TEXT NOT NULL,
            platform TEXT,
            modules TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(python_version, modules)
        )
    ''')
    
    # Errors table
    c.execute('''
        CREATE TABLE IF NOT EXISTS errors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            error_name TEXT NOT NULL,
            description TEXT,
            error_type TEXT,
            traceback TEXT,
            fix TEXT,
            complexity TEXT,
            status TEXT DEFAULT 'Open',
            tags TEXT,
            environment_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (environment_id) REFERENCES environments (id)
        )
    ''')
    
    conn.commit()
    conn.close()

def get_current_environment():
    """Get current Python environment info"""
    modules = {}
    try:
        import pkg_resources
        installed_packages = pkg_resources.working_set
        modules = {d.project_name: d.version for d in installed_packages}
    except:
        pass
    
    return {
        'python_version': sys.version.split()[0],
        'platform': platform.platform(),
        'modules': json.dumps(modules, sort_keys=True)
    }

def get_or_create_environment(env_info):
    """Get existing environment or create new one"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''
        SELECT id FROM environments 
        WHERE python_version = ? AND modules = ?
    ''', (env_info['python_version'], env_info['modules']))
    
    result = c.fetchone()
    
    if result:
        env_id = result[0]
    else:
        c.execute('''
            INSERT INTO environments (python_version, platform, modules)
            VALUES (?, ?, ?)
        ''', (env_info['python_version'], env_info['platform'], env_info['modules']))
        env_id = c.lastrowid
    
    conn.commit()
    conn.close()
    return env_id

def save_error(error_data):
    """Save error to database"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    tags_str = json.dumps(error_data.get('tags', [])) if error_data.get('tags') else None
    
    c.execute('''
        INSERT INTO errors (
            error_name, description, error_type, traceback, 
            fix, complexity, status, tags, environment_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        error_data['error_name'],
        error_data.get('description'),
        error_data.get('error_type'),
        error_data.get('traceback'),
        error_data.get('fix'),
        error_data.get('complexity'),
        error_data.get('status', 'Open'),
        tags_str,
        error_data.get('environment_id')
    ))
    
    conn.commit()
    conn.close()

def get_all_errors():
    """Get all errors with environment info"""
    conn = sqlite3.connect(DB_PATH)
    
    query = '''
        SELECT 
            e.id,
            e.error_name,
            e.description,
            e.error_type,
            e.traceback,
            e.fix,
            e.complexity,
            e.status,
            e.tags,
            e.created_at,
            e.updated_at,
            env.python_version,
            env.platform
        FROM errors e
        LEFT JOIN environments env ON e.environment_id = env.id
        ORDER BY e.created_at DESC
    '''
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if not df.empty and 'tags' in df.columns:
        df['tags'] = df['tags'].apply(lambda x: json.loads(x) if x else [])
    
    return df

def get_all_environments():
    """Get all environments"""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query('SELECT * FROM environments ORDER BY created_at DESC', conn)
    conn.close()
    return df

def get_errors_by_environment(env_id):
    """Get errors for a specific environment"""
    conn = sqlite3.connect(DB_PATH)
    
    query = '''
        SELECT 
            e.id,
            e.error_name,
            e.description,
            e.error_type,
            e.traceback,
            e.fix,
            e.complexity,
            e.status,
            e.tags,
            e.created_at,
            e.updated_at
        FROM errors e
        WHERE e.environment_id = ?
        ORDER BY e.created_at DESC
    '''
    
    df = pd.read_sql_query(query, conn, params=(env_id,))
    conn.close()
    
    if not df.empty and 'tags' in df.columns:
        df['tags'] = df['tags'].apply(lambda x: json.loads(x) if x else [])
    
    return df

# Initialize database
init_db()

# Main app
st.title("🐛 Error Logger")
st.markdown("Log and track errors with environment information")

# Sidebar navigation
page = st.sidebar.selectbox("Navigation", ["Log Error", "View Errors", "Environments", "Search & Filter"])

if page == "Log Error":
    st.header("Log New Error")
    
    # Get current environment
    current_env = get_current_environment()
    
    with st.expander("Current Environment Info", expanded=False):
        st.json(current_env)
    
    # Auto-register current environment
    env_id = get_or_create_environment(current_env)
    st.info(f"📌 Current environment ID: {env_id}")
    
    with st.form("error_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            error_name = st.text_input("Error Name *", placeholder="e.g., ValueError: invalid literal")
            error_type = st.text_input("Error Type", placeholder="e.g., ValueError, TypeError, etc.")
            complexity = st.selectbox("Complexity", ["Low", "Medium", "High", "Critical"])
            status = st.selectbox("Status", ["Open", "In Progress", "Resolved", "Won't Fix"])
        
        with col2:
            tags_input = st.text_input("Tags (comma-separated)", placeholder="e.g., database, api, authentication")
            use_current_env = st.checkbox("Link to current environment", value=True)
            custom_env_id = None
            if not use_current_env:
                envs = get_all_environments()
                if not envs.empty:
                    env_options = [f"ID {row['id']}: Python {row['python_version']}" for _, row in envs.iterrows()]
                    selected_env = st.selectbox("Select Environment", env_options)
                    custom_env_id = int(selected_env.split(":")[0].replace("ID ", ""))
        
        description = st.text_area("Description *", height=100, placeholder="Describe the error and when it occurs...")
        traceback = st.text_area("Traceback", height=150, placeholder="Paste the full traceback here...")
        fix = st.text_area("Fix/Solution", height=150, placeholder="Describe the fix or solution...")
        
        submitted = st.form_submit_button("Save Error", type="primary")
        
        if submitted:
            if not error_name or not description:
                st.error("Please fill in required fields: Error Name and Description")
            else:
                tags = [tag.strip() for tag in tags_input.split(",")] if tags_input else []
                
                error_data = {
                    'error_name': error_name,
                    'description': description,
                    'error_type': error_type if error_type else None,
                    'traceback': traceback if traceback else None,
                    'fix': fix if fix else None,
                    'complexity': complexity,
                    'status': status,
                    'tags': tags,
                    'environment_id': env_id if use_current_env else custom_env_id
                }
                
                save_error(error_data)
                st.success("✅ Error logged successfully!")
                st.balloons()

elif page == "View Errors":
    st.header("All Errors")
    
    errors_df = get_all_errors()
    
    if errors_df.empty:
        st.info("No errors logged yet. Go to 'Log Error' to add your first error.")
    else:
        # Display summary
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Errors", len(errors_df))
        with col2:
            st.metric("Open", len(errors_df[errors_df['status'] == 'Open']))
        with col3:
            st.metric("Resolved", len(errors_df[errors_df['status'] == 'Resolved']))
        with col4:
            st.metric("Critical", len(errors_df[errors_df['complexity'] == 'Critical']))
        
        st.divider()
        
        # Display errors
        for idx, row in errors_df.iterrows():
            with st.expander(f"🔴 {row['error_name']} - {row['status']} ({row['complexity']})"):
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.write("**Description:**", row['description'] or "N/A")
                    if row['error_type']:
                        st.write("**Type:**", row['error_type'])
                    if row['traceback']:
                        st.code(row['traceback'], language='python')
                    if row['fix']:
                        st.write("**Fix:**", row['fix'])
                    if row['tags']:
                        st.write("**Tags:**", ", ".join(row['tags']))
                
                with col2:
                    st.write("**Created:**", pd.to_datetime(row['created_at']).strftime("%Y-%m-%d %H:%M"))
                    if row['python_version']:
                        st.write("**Python:**", row['python_version'])
                    if row['platform']:
                        st.write("**Platform:**", row['platform'])
                    st.write("**Environment ID:**", row.get('environment_id', 'N/A'))

elif page == "Environments":
    st.header("Environments")
    
    envs_df = get_all_environments()
    
    if envs_df.empty:
        st.info("No environments registered yet.")
    else:
        st.metric("Total Environments", len(envs_df))
        st.divider()
        
        for idx, row in envs_df.iterrows():
            with st.expander(f"Environment ID {row['id']} - Python {row['python_version']}"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**Python Version:**", row['python_version'])
                    st.write("**Platform:**", row['platform'])
                    st.write("**Created:**", pd.to_datetime(row['created_at']).strftime("%Y-%m-%d %H:%M"))
                
                with col2:
                    if row['modules']:
                        modules = json.loads(row['modules'])
                        st.write(f"**Installed Modules ({len(modules)}):**")
                        st.json(modules)
                
                # Show errors for this environment
                env_errors = get_errors_by_environment(row['id'])
                if not env_errors.empty:
                    st.write(f"**Errors in this environment ({len(env_errors)}):**")
                    for _, err in env_errors.iterrows():
                        st.write(f"- {err['error_name']} ({err['status']})")

elif page == "Search & Filter":
    st.header("Search & Filter Errors")
    
    errors_df = get_all_errors()
    
    if errors_df.empty:
        st.info("No errors to search.")
    else:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            search_term = st.text_input("Search by name or description")
        with col2:
            filter_status = st.multiselect("Filter by Status", errors_df['status'].unique().tolist())
        with col3:
            filter_complexity = st.multiselect("Filter by Complexity", errors_df['complexity'].unique().tolist())
        
        # Apply filters
        filtered_df = errors_df.copy()
        
        if search_term:
            mask = (
                filtered_df['error_name'].str.contains(search_term, case=False, na=False) |
                filtered_df['description'].str.contains(search_term, case=False, na=False)
            )
            filtered_df = filtered_df[mask]
        
        if filter_status:
            filtered_df = filtered_df[filtered_df['status'].isin(filter_status)]
        
        if filter_complexity:
            filtered_df = filtered_df[filtered_df['complexity'].isin(filter_complexity)]
        
        st.write(f"**Found {len(filtered_df)} error(s)**")
        st.divider()
        
        if not filtered_df.empty:
            # Display filtered results
            for idx, row in filtered_df.iterrows():
                with st.expander(f"🔴 {row['error_name']} - {row['status']} ({row['complexity']})"):
                    st.write("**Description:**", row['description'] or "N/A")
                    if row['error_type']:
                        st.write("**Type:**", row['error_type'])
                    if row['fix']:
                        st.write("**Fix:**", row['fix'])
                    if row['python_version']:
                        st.write("**Python Version:**", row['python_version'])
        else:
            st.warning("No errors match your filters.")

# Footer
st.sidebar.divider()
st.sidebar.markdown("**Error Logger v1.0**")
st.sidebar.markdown("Track and manage your errors efficiently")

