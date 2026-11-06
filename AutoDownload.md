# Auto Download

Hanin Scale Manage Software v2.451. The green **Auto Download** button opens the **Download Task** window.

The operation manual (`SyncTool Scale Management Software Operation Manual-20241120.pdf`) does not describe this window. The English captions are translations. The Chinese captions, and the program log, are the reliable names for each option.

In this software, **download** means two steps:

1. Read products into SyncTool’s local database.
2. Send that data to the scales that are already set up in the program.

While a download is running, other download actions wait until it finishes.

Settings are stored in `C:\Program Files (x86)\SyncTool\Config\AutoDown_Config.ini`. The run log is under `C:\Program Files (x86)\SyncTool\Program\Win32\_Log_DownloadFromFTP`.

The four titles at the top of the window (**File Source**, **All Data**, **Execution mode**, **Param Mode**) are sections of the same form.

## File Source

Where the scheduled download reads products from. One source is selected at a time.

| English label | Chinese meaning | What it does |
| --- | --- | --- |
| **Local File** | Import from a local file | Read a file on this computer. |
| **Client DB** | Import from a third-party database | Read from another program’s database. This option replaces the file fields with database fields. |
| **File Addr** | Local file path | Path of the file used by the schedule. |
| **Select** | Choose | Pick that file. |

**Client DB** shows these fields, which stay hidden while **Local File** is selected:

| English label | Chinese meaning | What it does |
| --- | --- | --- |
| **Server Name** | Server name | Database server. |
| **DB Name** | Database name | Database to read. |
| **User Name** | Login name | Login for that database. |
| **Password** | Password | Password for that login. |
| **Port** | Port | Server port. |
| **Connection Test** | Connection test | Checks the login. The result is **Connect Success** or **Connect Fail**. |
| **Sql Setting** | Script setup | SQL script that reads the products. If the script is empty, the download fails. |

On this computer the source is **Local File**, and **File Addr** is empty. With **Abnormal Download** turned on, the log then repeats `cannot find file which to be download` about once a second, because there is no file to read.

The file is parsed with an import template. This installation uses the template named **REGOS** (id 27): a `.txt` file, tab-separated, with a header row. The columns are the PLU fields, starting with `LFCode`, `ItemCode`, `Department`, `Name1`, `Name2`, `Name3`, label, barcode type, price, and weight unit. A file that does not match the template is rejected.

## All Data

A full catalog load. This is separate from the clock in **Execution mode**.

| English label | Chinese meaning | What it does |
| --- | --- | --- |
| **Down Full Data Daily** | Download the full data automatically every day | Once a day, at the time beside this box, import the whole file and send the whole catalog to the scales. The log calls this `All Down`. |
| Time next to that box | Time of the daily full download | Saved as `DownAllTime`. The window shows `00:00`. |
| **Clear Local DB** | Empty the local database | Before a full download, delete the products already stored in SyncTool. Products that are not in the file are then gone. The log line is `delete data before Down All`. Leave this off unless the file is the complete catalog. |
| **Local File** (second path) | Local file for the full import | A separate path from **File Addr**. Used by **Import Full Data** and by the daily full download. |
| **Import Full Data** | Full import for store opening | Imports that file immediately. It does not wait for the schedule. Use it for the first load of a scale. |

**Down Full Data Daily** is off on this computer, so no full download is scheduled.

## Execution mode

When the scheduled (not the once-a-day full) download runs. These three choices are alternatives. Only one is active.

| English label | Chinese meaning | What it does |
| --- | --- | --- |
| **Exec Download** | Start the schedule | Master switch. Checked, the schedule is allowed to run. Unchecked, it does not run. |
| **Abnormal Download** | Change download (异动下载) | The English word is a bad translation. This is not an error mode. SyncTool looks about once a second for a new or changed source file. Changed products are imported and sent to the scales. Unchanged products are left as they are. It does not wait for a clock time. |
| **Auto Down By Day** | Automatic download every day | Once a day, at the time beside this option, run the same change download. |
| **Auto Down By Miniute** | Download every few minutes | The label is a typo for “minute”. Repeat the change download every N minutes. The number beside it is N. The smallest useful value is 1. |
| **Start time** … **~** | Daily start time and end time | Daily window for **Auto Down By Minute**. The job runs only between these times. The program’s built-in default window is 08:00–20:00. |

A change download compares each product with the local database (an MD5 checksum). Only different rows are written. The log calls this job `Inc Down` and `Import increment data`. After the import it sends the result to the scales (`Down Data`).

On this computer **Exec Download** is on and **Abnormal Download** is selected. **Auto Down By Day** and **Auto Down By Minute** are off. The minute box still shows `1`, and the window is `00:00`–`23:59`, but those apply only after **Auto Down By Minute** is selected. With no file path, the change download finds nothing to read.

Opening another download pauses this schedule. Closing **Auto Download** reads the settings again and lets the schedule continue.

## Param Mode

| English label | Chinese meaning | What it does |
| --- | --- | --- |
| **Show Download Progress** | Show a progress window during automatic download | Checked, a window titled **Auto Download Progress** stays open during the job. Unchecked, the job runs without that window. |

It is unchecked on this computer.

## Which option to use

- First load of a scale: set the full-import file, then click **Import Full Data**. Turn on **Clear Local DB** only when that file should replace every product already in SyncTool.
- Keep scales aligned with a file that is rewritten through the day: **Exec Download** + **Abnormal Download**, and set **File Addr** to that file.
- Send changes once a day: **Exec Download** + **Auto Down By Day**, and set the time.
- Send changes all day on a timer: **Exec Download** + **Auto Down By Minute**, set the interval, and set **Start time**.
- Once a day, also push the entire catalog: turn on **Down Full Data Daily** and set its time. This can sit on top of a change schedule.
