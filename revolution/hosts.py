from django_hosts import patterns, host

host_patterns = patterns(
    '',
    host(r'www', 'revolution.urls', name='www'),
    host(r'', 'revolution.urls', name='default'),
    host(r'aapp', 'Aapp.urls', name='aapp'),
)
