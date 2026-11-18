import cv2, numpy as np, json
im=cv2.imread('modelo/Map-COL.jpg'); core=cv2.imread('mask_brow1k.png',0)
L=cv2.cvtColor(im,cv2.COLOR_BGR2LAB)[...,0].astype(float); loc=cv2.GaussianBlur(L,(0,0),12)
near=cv2.dilate(core,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(27,27)))
weak=(((loc-L)>5)&(near>0)).astype(np.uint8)*255
rem=cv2.dilate(cv2.bitwise_or(core,weak),cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(7,7)))
# pontos vermelhos das pálpebras
hsv=cv2.cvtColor(im,cv2.COLOR_BGR2HSV); red=((hsv[...,1]>90)&(hsv[...,0]<12)&(hsv[...,2]>150)).astype(np.uint8)*255
red[:280]=0; red[330:]=0; red[:, :420]=0; red[:, 620:]=0; red=cv2.dilate(red,np.ones((7,7),np.uint8))
print('red px',int((red>0).sum()))
sr=cv2.dnn_superres.DnnSuperResImpl_create(); sr.readModel('/root/.docon/models/EDSR_x4.pb'); sr.setModel('edsr',4)
up=sr.upsample(im); print(up.shape)
M=cv2.resize(cv2.bitwise_or(rem,red),(4096,4096),interpolation=cv2.INTER_LINEAR); M=(M>60).astype(np.uint8)*255
y0,y1,x0,x1=880,1360,1380,2700
crop=up[y0:y1,x0:x1].copy(); mc=M[y0:y1,x0:x1]
small=cv2.resize(crop,None,fx=.25,fy=.25,interpolation=cv2.INTER_AREA); ms=cv2.resize(mc,None,fx=.25,fy=.25,interpolation=cv2.INTER_NEAREST)
inp=cv2.inpaint(small,ms,9,cv2.INPAINT_TELEA); inp=cv2.resize(inp,(crop.shape[1],crop.shape[0]),interpolation=cv2.INTER_CUBIC)
inp=cv2.GaussianBlur(inp,(0,0),6)
# poros: alta frequência da testa (acima das sobrancelhas), repetida em ladrilho
src=up[700:860,1500:2600].astype(np.float32); hf=src-cv2.GaussianBlur(src,(0,0),5)
tile=np.tile(hf,(4,2,1))[:crop.shape[0],:crop.shape[1]]
a=cv2.GaussianBlur(mc.astype(np.float32)/255,(0,0),10)[...,None]
out=crop.astype(np.float32)*(1-a)+(inp.astype(np.float32)+tile*0.9)*a
up[y0:y1,x0:x1]=np.clip(out,0,255).astype(np.uint8)
cv2.imwrite('pele4k.jpg',up,[cv2.IMWRITE_JPEG_QUALITY,93])
core4=cv2.resize(core,(4096,4096),interpolation=cv2.INTER_LINEAR); cv2.imwrite('brow4k.png',core4[y0:y1,x0:x1])
json.dump({'x0':x0,'y0':y0,'w':x1-x0,'h':y1-y0},open('regiao.json','w'))
cv2.imwrite('chk_pele.jpg',up[y0:y1,x0:x1])
