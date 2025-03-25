#!/usr/bin/env python3
"""
Script to import CPV codes from an XML file into the database.
This script extracts the code, English description (from Name or en_label),
and Spanish description (from es_label) from the CPV XML file.

Usage:
    python import_cpv_codes.py [path_to_xml_file]

If no path is provided, it will look for a file named 'cpv.gc' in the current directory.
"""

import os
import sys
import logging
import xml.etree.ElementTree as ET
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

# Add the project root directory to Python's path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.database import SessionLocal
from app.modules.auth.models import CpvCode

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# XML namespace
NAMESPACE = {'gc': 'http://docs.oasis-open.org/codelist/ns/genericode/1.0/'}

def parse_cpv_xml(xml_file_path):
    """
    Parse the CPV XML file and extract the code, English description, and Spanish description.
    
    Args:
        xml_file_path: Path to the CPV XML file
        
    Returns:
        List of dictionaries containing code, description, and es_description
    """
    logger.info(f"Parsing XML file: {xml_file_path}")
    
    try:
        # Parse the XML file
        tree = ET.parse(xml_file_path)
        root = tree.getroot()
        
        # Print root element and namespace info for debugging
        logger.info(f"Root element: {root.tag}")
        logger.info(f"Namespaces: {root.nsmap if hasattr(root, 'nsmap') else 'Not available'}")
        
        # Try different namespace approaches
        # First, try with namespace prefixes
        rows = root.findall('.//gc:SimpleCodeList/gc:Row', NAMESPACE)
        
        # If no rows found, try without namespace prefix for SimpleCodeList and Row
        if not rows:
            logger.info("No rows found with namespace prefix. Trying without namespace for SimpleCodeList and Row...")
            rows = root.findall('.//SimpleCodeList/Row', NAMESPACE)
        
        # If still no rows, try a more flexible approach
        if not rows:
            logger.info("Still no rows found. Trying with local-name()...")
            # This is a more complex but flexible way to find elements regardless of namespace
            # Since ElementTree doesn't support local-name(), we'll do a more brute-force approach
            simple_code_lists = []
            for child in root.iter():
                if child.tag.endswith('SimpleCodeList'):
                    simple_code_lists.append(child)
            
            rows = []
            for scl in simple_code_lists:
                for child in scl.iter():
                    if child.tag.endswith('Row'):
                        rows.append(child)
            
            logger.info(f"Found {len(rows)} rows using tag suffix matching")
        
        logger.info(f"Found {len(rows)} CPV code entries in the XML file")
        
        cpv_codes = []
        for row in rows:
            code = None
            description = None
            es_description = None
            
            # Try different ways to find Value elements
            values = row.findall('.//gc:Value', NAMESPACE)
            if not values:
                values = row.findall('.//Value', NAMESPACE)
            
            if not values:
                # Brute force approach if the above fails
                values = []
                for child in row.iter():
                    if child.tag.endswith('Value'):
                        values.append(child)
            
            for value in values:
                column_ref = value.get('ColumnRef')
                
                # Try different ways to find SimpleValue
                simple_value = value.find('.//gc:SimpleValue', NAMESPACE)
                if simple_value is None:
                    simple_value = value.find('.//SimpleValue')
                
                if simple_value is None:
                    # Brute force approach
                    for child in value.iter():
                        if child.tag.endswith('SimpleValue'):
                            simple_value = child
                            break
                
                if simple_value is not None and simple_value.text is not None:
                    if column_ref == 'Code':
                        code = simple_value.text
                    elif column_ref == 'Name':
                        description = simple_value.text
                    elif column_ref == 'en_label':
                        # If Name is not available, use en_label
                        if description is None:
                            description = simple_value.text
                    elif column_ref == 'es_label':
                        es_description = simple_value.text
            
            if code:
                cpv_codes.append({
                    'code': code,
                    'description': description,
                    'es_description': es_description
                })
        
        logger.info(f"Successfully parsed {len(cpv_codes)} CPV codes")
        return cpv_codes
    
    except Exception as e:
        logger.error(f"Error parsing XML file: {str(e)}")
        logger.exception("Full traceback:")
        raise

def import_cpv_codes_to_db(cpv_codes):
    """
    Import the CPV codes into the database.
    
    Args:
        cpv_codes: List of dictionaries containing code, description, and es_description
        
    Returns:
        Number of CPV codes imported
    """
    logger.info(f"Importing {len(cpv_codes)} CPV codes to the database")
    
    db = SessionLocal()
    count_inserted = 0
    count_updated = 0
    
    try:
        # Process each CPV code
        for cpv_data in cpv_codes:
            code = cpv_data['code']
            description = cpv_data['description']
            es_description = cpv_data['es_description']
            
            # Check if code already exists
            existing_code = db.query(CpvCode).filter(CpvCode.code == code).first()
            
            if existing_code:
                # Update existing code
                existing_code.description = description
                existing_code.es_description = es_description
                count_updated += 1
            else:
                # Create new code
                new_code = CpvCode(
                    code=code,
                    description=description,
                    es_description=es_description
                )
                db.add(new_code)
                count_inserted += 1
            
            # Commit every 100 records
            if (count_inserted + count_updated) % 100 == 0:
                db.commit()
                logger.info(f"Processed {count_inserted + count_updated} CPV codes")
        
        # Commit any remaining records
        db.commit()
        logger.info(f"Import completed. Inserted: {count_inserted}, Updated: {count_updated}")
        
        return count_inserted + count_updated
    
    except Exception as e:
        logger.error(f"Error importing CPV codes: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()

def main():
    """
    Main function to import CPV codes from an XML file.
    """
    # Check for debug flag
    debug_mode = "--debug" in sys.argv
    if debug_mode:
        # Set logging to debug level
        logger.setLevel(logging.DEBUG)
        sys.argv.remove("--debug")
    
    # Get XML file path from command-line argument or use default
    if len(sys.argv) > 1 and not sys.argv[1].startswith("--"):
        xml_file_path = sys.argv[1]
    else:
        xml_file_path = 'cpv.gc'
    
    # Check if file exists
    if not os.path.isfile(xml_file_path):
        logger.error(f"XML file not found: {xml_file_path}")
        sys.exit(1)
    
    # Log file stats
    file_size = os.path.getsize(xml_file_path) / (1024 * 1024)  # Size in MB
    logger.info(f"XML file size: {file_size:.2f} MB")
    
    try:
        # If in debug mode, dump the first 2000 characters of the file
        if debug_mode:
            with open(xml_file_path, 'r', encoding='utf-8') as f:
                content = f.read(2000)
                logger.debug(f"First 2000 characters of the file:\n{content}")
        
        # Parse the XML file
        cpv_codes = parse_cpv_xml(xml_file_path)
        
        if not cpv_codes:
            logger.warning("No CPV codes were found to import. Check that the XML file has the expected structure.")
            if "--force-import" in sys.argv:
                logger.info("Force import flag detected. Continuing with empty set...")
            else:
                logger.info("Use --force-import to proceed with an empty set, or fix the data source.")
                sys.exit(1)
        
        # Import the CPV codes to the database
        count = import_cpv_codes_to_db(cpv_codes)
        
        logger.info(f"Successfully imported {count} CPV codes")
    
    except Exception as e:
        logger.error(f"Import failed: {str(e)}")
        if debug_mode:
            logger.exception("Detailed traceback:")
        sys.exit(1)

if __name__ == "__main__":
    main() 