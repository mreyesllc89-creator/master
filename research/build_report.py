import json, sys
data = open(sys.argv[1]).read()
tpl = open(sys.argv[2]).read()
open(sys.argv[3], 'w').write(tpl.replace('__DATA__', data))
