# Design

``` mermaid
erDiagram
	dataset ||--o{ upload : contains
	dataset ||--o{ dataset_part : comprises
	tag }o--o{ dataset : tracks
```

## Full database diagram

!!! note
	This has been auto-generated from the SQLite database.
	It isn't laid out very sensibly,
	and is probably out of date,
	but may be helpful anyway.
	
	Click on the image to zoom in.
	
[![Database schema diagram](diagrams/db.svg)](diagrams/db.svg)
