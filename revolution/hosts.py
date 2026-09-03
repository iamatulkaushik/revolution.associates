from django_hosts import patterns, host

host_patterns = patterns(
    '',
    host(r'www', 'revolution.urls', name='www'),
    host(r'sapp', 'Sapp.urls', name='sapp'),
    host(r'aapp', 'Aapp.urls', name='aapp'),
    host(r'capp', 'Capp.urls', name='capp'),
    host(r'cxapp', 'Cxapp.urls', name='cxapp'),
    host(r'', 'revolution.urls', name='default'),
)
