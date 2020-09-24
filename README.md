# PinSync
A lightweight tool to download and sync Pinterest image boards to local storage.

## Functionality
Beyond simple sync operations, PinSync includes functionality to (1) detect and push to Pinterest local deletions that have been performed manually between syncs, allowing the user to prune their boards/sections locally and have these changes reflected on Pinterest, and (2) detect and delete duplicate images, removing the need to manually comb through each board individually searching for duplicates.

## Contents
PinSync contains 3 main classes, Pin, Image, and Container, with a Client control class to tie the objects together. Pins and Images represent pinterest and local objects respectively, while Containers collate both of these and serve as a bridge between pinterest API interactions and local file manipulation. Containers come in two forms, Boards and Sections, mirroring the structures used by Pinterest itself. Boards and Sections both implement the same set of generic methods, with Boards adding only a get_sections() method to retrieve the sections stored within them.

A complete list of objects and their associated functions is provided below for reference:

### Pin
Pins represent objects that are present on the Pinterest account of the currently logged-in user, but not necessarily on local storage. Fields and member functions include:

```
  Pin.name          # name <str> of pin on Pinterest
  Pin.id            # id <str> of pin on Pinterest
  Pin.description   # description <str> (if any) of pin on Pinterest
  Pin.board_name    # name <str> of board which the pin belongs to
  Pin.section_name  # name <str | None> of section (if any) that the pin is contained within
  Pin.url           # url <str> linking to highest available resolution of the pinned image
  Pin.extension     # file extension <str> of pinned image (ex: .jpeg, .png, ...)
  Pin.image_height  # height <int> in pixels of pinned image
  Pin.image_width   # width <int> in pixels of pinned image
  Pin.download_dir  # path <str> to local directory in which to save the pinned image
  Pin.image_path    # path <str> to image on local storage

  Pin.download()
    # Downloads pin to current working directory, within a directory structure that mirrors the arrangement found on Pinterest.
  
  Pin.to_json()
    # Translates the pin's fields to a storable json structure.  This is used primarily for detecting and mirroring local changes made between sync operations.
```

### Image
Images represent files that are present on local storage, but not necessarily on the Pinterest account of the currently logged-in user. Fields and member functions include:

```
  Image.id            # id <str> of saved image
  Image.path          # path <str> to saved image on local storage
  Image.board_name    # name <str> of board **directory** under which this image is stored
  Image.section_name  # name <str | None> of section (if any) under which this image is stored
  Image.hash          # hash <int> of saved image.  Computed as a difference hash
  Image.height        # height <int> in pixels of saved image
  Image.width         # width <int> in pixels of saved image
  Image.size          # total pixel count <int> of image (height x width)
  Image.color         # average color of saved image
  
  Image.is_similar_to(Image, threshold=3)
    # Compares image similarity.  Returns True if passed Image's hash is within threshold units of this image's hash.
  
  Image.to_json()
    # Translates this image's fields to a storable json structure.
```

### Container
Containers are the primary unit of PinSync's operation and serve as a bridge between Pins and Images. Containers come in two forms, Board and Section, which differ only by one function. Everything else is identical between the two. Fields and member functions include:

```
  Container.client    # pinterest api client for currently logged-in user (for internal use)
  Container.name      # name <str> of container
  Container.path      # path <str> on local storage of corresponding container
  Container.id        # id <str> of container on Pinterest
  Container.pins      # list <Pin> of pins stored within this container
  Container.images    # list <Image> of saved image within this container on local storage
  Container.old       # list <json> of saved images present within this container after the last sync operation.  Used to detect local changes.
  
  Container.delete_pin(pin_id)
    # deletes pin from this container and from Pinterest
  
  Container.delete_image(image_id)
    # deletes image from this container and from local storage
  
  Container.size()
    # number <int> of pins observed on Pinterest for this container
  
  Container.get_differences()
    # returns tuple of lists of [1] pins not present on local storage and [2] images not present on Pinterest
    
  Container.manually_deleted()
    # scans Container.old for images which have been manually deleted by the user since the last sync operation.  Returns these as a list
  
  Container.push_local_changes()
    # calls above function.  If any deletions are found, prompts the user whether to ignore or mirror these alterations to Pinterest.
    
  Container.duplicate_images()
    # scans Container.images for images which have a hash collision with at least one other image within the same list.  These are returned in a dictionary mapping the hash to its respective images.
    
  Container.remove_duplicates()
    # calls above function, removing any duplicates that are encountered.  The choice of which image to keep is done on a priority basis, with higher-resolution and older pins being favored (in that order).
    
  Container.save_manifest()
    # collects images, converts them to json format, and dumps the contents to a manifest.json file which sits alongside the images themselves.  This manifest file is then read to form Container.old upon initialization.
    
  Container.sync()
    # the meat of the object.  Syncs the container's contents between Pinterest and local storage.  The algorithm is as follows:
        1.  Search for and handle manual deletions via Container.push_local_changes()
        2.  Gather differences via Container.get_differences()
        3.  Delete local images that are not present on Pinterest
        4.  Download pins that are not stored on local storage
        5.  Save manifest for future reference
        
  
  # There is one additional function for Boards that is not present for sections
  Board.get_sections()
    # returns list of Sections stored within this Board.
```

### Client
Client is a lightweight control class meant to wrap around the above objects and initialize them according to the structure found on Pinterest. In true Object-Oriented fashion, it does next to nothing on its own. Member functions are provided below:

```
  Client.get_boards()
    # returns a list of all Board objects found in the currently logged-in user's profile
  
  Client.find(board_name, section_name=None, pin_id=None)
    # searches for and returns the given board/section/pin within the current Container hierarchy
   
  Client.logout()
    # closes the current Pinterest connection
```

# DISCLAIMER
USE AT YOUR OWN RISK! Use of this tool comes with the chance of accidentally deleting pins which you may not want to lose. It is highly advised that you back up your boards before tinkering with this library.
