import inspect
import youtool

print('youtool module:', youtool)
names = [n for n in dir(youtool) if not n.startswith('_')]
print('names:', names)

for target in ('YouTube', 'parse_channel_data'):
    if hasattr(youtool, target):
        obj = getattr(youtool, target)
        print('\n==', target, '==')
        print('callable?', callable(obj))
        try:
            src = inspect.getsource(obj)
            print(src[:2000])
        except Exception as e:
            print('source unavailable or too large:', e)
    else:
        print('\n==', target, 'not found')

# Try using YouTube to get channel info for 'Ludwig'
if hasattr(youtool, 'YouTube'):
    try:
        yt = youtool.YouTube()
        print('\nYouTube() instantiated:', yt)
        # try a method that might exist
        if hasattr(yt, 'channel'):
            try:
                res = yt.channel('Ludwig')
                print('yt.channel("Ludwig") ->', type(res), repr(res)[:500])
            except Exception as e:
                print('error calling yt.channel:', e)
    except Exception as e:
        print('error instantiating YouTube:', e)
