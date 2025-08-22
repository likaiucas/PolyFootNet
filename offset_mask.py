"""
For the RAG, 
Solving BFE with building mask and offset
"""
import json
import cv2
import numpy as np
from copy import copy
import math
from pycocotools.coco import COCO
from pycocotools import mask as maskUtils
from tqdm import tqdm
from multiprocessing import Pool
from skimage.measure import label, regionprops

def wapper(args):
    fun, ann, keys = args
    x = ann[keys]
    y = ann['offset']
    ann['building_seg'] = ann[keys]
    ann['building_bbox'] = get_bboxes(decode_rle(ann[keys]))
    roof, foot = fun(x,y)
    ann['roof_mask'] = roof
    ann['roof_bbox']=get_bboxes(decode_rle(roof))
    ann['bbox']=ann['roof_bbox']
    ann['segmentation'] = ann['roof_mask']
    ann['footprint_mask'] = foot
    return ann

def get_bboxes(seg_results):
    np_array = seg_results
    labeled_image = label(np_array.astype(np.uint8))
    regions = regionprops(labeled_image)
    bounding_boxes = [region.bbox for region in regions ]  # (min_row, min_col, max_row, max_col)if filter_region(region)
    if (0,0,1024,1024) in bounding_boxes:
        bounding_boxes.remove((0,0,1024,1024))
    if (0,0,512,512) in bounding_boxes:
        bounding_boxes.remove((0,0,1024,1024))
    bounding_boxes = [[bbox[1], bbox[0], bbox[3], bbox[2]] for bbox in bounding_boxes]  # (min_x, min_y, max_x, max_y)
    areas = [region.area for region in regions]
    if areas == []:
            return []
    max_id = np.argmax(areas)
    return bounding_boxes[max_id]

def numpy_mask_to_coco_rle(binary_mask):
    rle = maskUtils.encode(np.array(binary_mask, order='F', dtype=np.uint8))
    rle['counts'] = rle['counts'].decode('ascii')
    return rle

def decode_rle(ann):
    rle = [ann] if not isinstance(ann, list) else ann
    rle = maskUtils.merge(rle)
    binary_mask = maskUtils.decode(rle)     
    return binary_mask

def decode_polygon(ann):
    rle = maskUtils.frPyObjects(ann, 1024, 1024)
    rle = maskUtils.merge(rle)
    binary_mask = maskUtils.decode(rle)
    return binary_mask

def get_roof(mask_ann, offset):
    try:
        binary_mask = decode_rle(mask_ann)
    except:
        binary_mask = decode_polygon(mask_ann)
    # reco = bin
    translation_matrix = np.float32([[1,0,-offset[0]],[0,1,-offset[1]]])
    foot_ = cv2.warpAffine(binary_mask, translation_matrix, (1024,1024))
    translation_matrix = np.float32([[1,0,offset[0]],[0,1,offset[1]]])
    roof_ = cv2.warpAffine(binary_mask, translation_matrix, (1024,1024))
    foot = cv2.bitwise_and(foot_, binary_mask)
    roof = cv2.bitwise_and(roof_, binary_mask)
    return numpy_mask_to_coco_rle(roof), numpy_mask_to_coco_rle(foot)

def main(js_path, output_path=None, buil_key=None):
    keys = buil_key if buil_key else 'segmentation'
    js = json.load(open(js_path, 'r'))
    anns = js['annotations'] if isinstance(js, dict) else js
    inputs = [(get_roof, ann, keys) for ann in anns]
    pool = Pool(16)
    anns_out = pool.map(wapper, inputs)
    if isinstance(js, dict):
        js['annotations'] = anns_out
    else:
        js = anns_out
    # for ann in tqdm(anns):
    #     mask_ann = ann['building_seg']
    #     offset = ann['offset']  
    #     roof, foot = get_roof(mask_ann, offset)
    #     ann['roof_mask'] = roof
    #     ann['footprint_mask'] = foot
    if output_path:
        with open(output_path, 'w') as f:
            json.dump(js, f)
    else:
        with open('builoffset.json', 'w') as f:
            json.dump(js, f)
def move_pkl(items):
    bbox, c, masks, offsets = items
    roof_masks = []
    for mask, offset in zip(masks[0], offsets):
        m = decode_rle(mask)
        translation_matrix = np.float32([[1,0,offset[0]],[0,1,offset[1]]])
        roof_ = cv2.warpAffine(m, translation_matrix, (1024,1024))
        roof = cv2.bitwise_and(roof_, m)
        roof_masks.append(numpy_mask_to_coco_rle(roof))
    return (bbox, c, [roof_masks], offsets)

def main_pkl(pkl_path, output_path=None):
    import pickle
    with open(pkl_path, 'rb') as f:
        pkl = pickle.load(f)
    pool = Pool(16)
    outs = pool.map(move_pkl, pkl)
    # outs = []
    # for bbox, c, masks, offsets in tqdm(pkl):
    #     roof_masks = []
    #     for mask, offset in zip(masks[0], offsets):
    #         m = decode_rle(mask)
    #         translation_matrix = np.float32([[1,0,offset[0]],[0,1,offset[1]]])
    #         roof_ = cv2.warpAffine(m, translation_matrix, (1024,1024))
    #         roof = cv2.bitwise_and(roof_, m)
    #         roof_masks.append(numpy_mask_to_coco_rle(roof))
    #     outs.append((bbox, c, [roof_masks], offsets))
    if output_path:
        with open(output_path, 'wb') as f:
            pickle.dump(outs, f)
    else:
        with open('builoffset.json', 'wb') as f:
            pickle.dump(outs, f)

def main_pkl_zero(pkl_path, output_path=None):
    import pickle
    with open(pkl_path, 'rb') as f:
        pkl = pickle.load(f)
    # pool = Pool(16)
    # outs = pool.map(move_pkl, pkl)
    outs = []
    for bbox, c, masks, offsets in tqdm(pkl):
        offsets = 0*offsets
        outs.append((bbox, c, masks, offsets))
    if output_path:
        with open(output_path, 'wb') as f:
            pickle.dump(outs, f)
    else:
        with open('builoffset.json', 'wb') as f:
            pickle.dump(outs, f)
if __name__=='__main__':
    # js_path = 'cascade_loft_r50_fpn_3x_buil.json'
    # main('cascade_loft_r50_fpn_buil_prompt.json', output_path='sw_cascade_loft_r50_fpn_buil_prompt.json')
    # main_pkl('./loft_foa_r50_fpn_2x_bonai_buil.pkl', output_path='./sw_loft_foa_r50_fpn_2x_bonai_buil.pkl')
    # main_pkl_zero('maskrcnn_r50_fpn_2x_bonai_huizhou.pkl', output_path='sw_maskrcnn_r50_fpn_2x_bonai_huizhou.pkl')
    # main('smlcdr_obm_auto_fpn_b_pretrained_poly_bonai_traindeco_forbase_SOFA.json', 'sw_smlcdr_obm_auto_fpn_b_pretrained_poly_bonai_traindeco_forbase_SOFA.json', buil_key='building_seg')
    main('smlcdr_obm_auto_fpn_b_pretrained_poly_bonai_traindeco_HTC.json', 'sw_smlcdr_obm_auto_fpn_b_pretrained_poly_bonai_traindeco_HTC.json', buil_key='building_seg')