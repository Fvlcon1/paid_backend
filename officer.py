from gpt import processor

def app(environ, start_response):
    """Minimal WSGI app to keep processor running"""
    status = '200 OK'
    response_headers = [('Content-type', 'text/plain')]
    start_response(status, response_headers)
    return [b"NHIS Claim Processor running in background\n"]

# Start the processor thread when module loads
if __name__ != "__main__":
    processor_thread = start_processor()