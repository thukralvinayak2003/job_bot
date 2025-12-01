import sys
print('cwd=', sys.path[0])
print('sys.path snippet:')
for p in sys.path[:5]:
    print(' -', p)
try:
    from scrapers import linkedin
    print('has_search_jobs=', hasattr(linkedin, 'search_jobs'))
    print('repr=', linkedin)
except Exception as e:
    print('import error:', repr(e))
    raise
