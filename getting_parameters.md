# Mapping command-line arguments to the needed parameters in the configuration file
* Clone the project [yt-dlp](https://github.com/yt-dlp/yt-dlp)
* Edit `YoutubeDL.py`
* Add two pieces of code:  
  * Directly before `class YoutubeDL:` (around line 200)
    ```
    class SetEncoder(json.JSONEncoder):
        def is_jsonable(self, x):
            try:
                json.dumps(x)
                return True
            except:
                return False
    
        def default(self, obj):
            if isinstance(obj, set):
                return list(obj)
            if not self.is_jsonable(obj):
                return 'NOT SERIALIZABLE: ' + type(obj).__name__
            return json.JSONEncoder.default(self, obj)
    ```

  * in `__init__()`, directly after `self.params = params` (around line 640)
    ```
    with open('yt-dl_params.json', 'w') as out_file:
        out_file.write(json.dumps(obj=params, indent=True, sort_keys=True, cls=SetEncoder))

    ```
* Run yt-dlp from where you cloned it with your desired arguments.  
  It will write the parameters into the file *yt-dl_params.json*  
  Unfortunately, a few things are written as `NOT SERIALIZABLE`.
  These values are currently unsupported by the GUI and need to be removed.  
  Everything else can directly be copied into your configuration file.
