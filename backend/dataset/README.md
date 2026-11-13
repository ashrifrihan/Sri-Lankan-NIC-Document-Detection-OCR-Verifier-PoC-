# Private NIC vision dataset

Keep all source images, exports and training runs outside this repository.
Use synthetic cards or authorized private images. Use opaque filenames and
group identifiers. Avoid NIC numbers and names in metadata and paths.

```text
private-dataset/
  detection/
    data.yaml
    images/{train,val,test}/
    labels/{train,val,test}/
  classification/
    {train,val,test}/{not_nic,old_laminated,printed_laminated,smart_card}/
  groups.csv
```

Use local Label Studio to draw a rectangular box around the whole card and
tight boxes around each visible field. Roboflow can export the same YOLO
format for synthetic data. Use synthetic images for external labeling tools.
Omit obscured fields and chips that are absent. Name and DOB boxes should
contain the printed value. Use empty detection labels for negative images.
Preserve this class-ID order in the export and in `data.yaml`.

```yaml
path: /absolute/path/to/private-dataset/detection
train: images/train
val: images/val
test: images/test
names:
  0: card
  1: nic_number
  2: name
  3: dob
  4: photo
  5: chip
```

Record `image,card_group,split` in the private manifest. Assign a split to the
card group before exporting any photos. Include both sides, repeated captures,
crops and synthetic derivatives in that same group. Share assignments between
the detector and classifier. Stratify by type where feasible and reserve test
groups until training and threshold selection finish. Populate each class in
training and validation. For classification, export card crops and include
negative examples such as unrelated documents and backgrounds.

Apply rotation, perspective, blur, glare and low-light variation only to the
training split. Transform boxes with the pixels for geometric changes. Simulate
glare with localized highlights, low light with brightness reduction, and blur
with Gaussian or motion kernels. Disable flips that mirror printed characters.
Keep validation and test photos representative of actual captures.

From `backend`, install `requirements-vision.txt` and run:

```text
python train_vision.py detector /private/detection/data.yaml /private/runs
python train_vision.py classifier /private/classification /private/runs
```

Use the detector's `best.pt` and the classifier's `classifier.pt` as
`NIC_DETECTOR_WEIGHTS` and `NIC_CLASSIFIER_WEIGHTS`. Restart the service after
changing weights. Load only trusted checkpoints. Without usable weights, the
verifier retains geometric crops and HSV classification.
