import cv2, numpy as np, json, math
R=json.load(open('regiao.json')); m=cv2.imread('brow4k.png',0); m=(m>100).astype(np.uint8)
cx=2048-R['x0']; rng=np.random.default_rng(11)
n,lab,st,cent=cv2.connectedComponentsWithStats(m); comps=[i for i in range(1,n) if st[i,4]>5000]
hairs=[]; meta=[]
for side,i in enumerate(sorted(comps,key=lambda i:cent[i][0])):
    mi=(lab==i).astype(np.uint8); mi=cv2.morphologyEx(mi,cv2.MORPH_CLOSE,np.ones((15,15),np.uint8))
    xs=np.where(mi.any(0))[0]; x0,x1=xs.min(),xs.max()
    top=np.array([np.where(mi[:,x])[0].min() if mi[:,x].any() else np.nan for x in range(x0,x1+1)],float)
    bot=np.array([np.where(mi[:,x])[0].max() if mi[:,x].any() else np.nan for x in range(x0,x1+1)],float)
    top=cv2.GaussianBlur(top[None],(1,0),9)[0] if False else np.convolve(np.nan_to_num(top,nan=np.nanmean(top)),np.ones(31)/31,'same')
    bot=np.convolve(np.nan_to_num(bot,nan=np.nanmean(bot)),np.ones(31)/31,'same')
    for k in range(15): top[k]=top[15]; bot[k]=bot[15]; top[-1-k]=top[-16]; bot[-1-k]=bot[-16]
    cen=(top+bot)/2; dc=np.gradient(np.convolve(cen,np.ones(41)/41,'same'))
    dl=-1 if (x0+x1)/2<cx else 1                       # lado de fora (lateral)
    med=x1 if dl==-1 else x0; Lb=x1-x0
    meta.append({'side':side,'x0':int(x0),'x1':int(x1),'dl':dl,'cy':float(np.mean(cen))})
    ring=cv2.dilate(mi,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(25,25)))-mi
    cnt=0; tries=0
    while cnt<1500 and tries<200000:
        tries+=1; x=rng.uniform(x0,x1); j=int(x-x0); t0,b0=top[j],bot[j]
        s=abs(x-med)/Lb
        # a cauda afina e sobe um pouco
        y=rng.uniform(t0-4,b0+4)
        inside=mi[int(np.clip(y,0,mi.shape[0]-1)),int(x)]>0
        if not inside:
            if not(ring[int(np.clip(y,0,mi.shape[0]-1)),int(x)] and rng.random()<0.05): continue
        r=np.clip((b0-y)/max(b0-t0,1),0,1)
        if s<0.18: th=math.radians(58-s/0.18*30)
        elif s<0.72: th=math.radians(22-36*r)
        else: th=math.radians(8-26*r-(s-0.72)*30)
        th+=math.radians(rng.normal(0,4.5))
        phi=math.atan2(-dc[j]*dl,dl); ang=phi+dl*th          # matemática (y para cima)
        a=-ang                                               # canvas (y para baixo)
        ln=(rng.uniform(26,44) if s<0.18 else rng.uniform(44,78))*(0.8 if not inside else 1)*(0.85 if s>0.85 else 1)
        w=rng.uniform(1.5,2.4)*(0.8 if not inside else 1)
        g=rng.random(); col=[int(38+30*g),int(27+20*g),int(22+14*g)] if rng.random()>0.15 else [int(95+30*g),int(80+20*g),int(70+15*g)]
        hairs.append({'x':round(x,1),'y':round(y,1),'a':round(a,3),'l':round(ln,1),'w':round(w,2),'c':round(float(rng.normal(0,0.12)),3),'col':col,'al':round(rng.uniform(.7,.9)*(0.62+0.38*min(1,s/0.22))*(0.85 if s>0.85 else 1),2),
                      'sd':side,'s':round(s,3),'r':round(float(r),3),'u':round(float(rng.random()),4),'v':round(float(rng.random()),4),'in':int(inside)})
        cnt+=1
json.dump({'regiao':R,'brows':meta,'hairs':hairs},open('fios.json','w'))
print(len(hairs),meta)
# teste de desenho
base=cv2.imread('pele4k.jpg')[R['y0']:R['y0']+R['h'],R['x0']:R['x0']+R['w']].copy()
from PIL import Image, ImageDraw
im=Image.fromarray(cv2.cvtColor(base,cv2.COLOR_BGR2RGB)).convert('RGBA'); lay=Image.new('RGBA',im.size,(0,0,0,0)); d=ImageDraw.Draw(lay)
for h in hairs:
    ex=h['x']+h['l']*math.cos(h['a']); ey=h['y']+h['l']*math.sin(h['a'])
    mx=(h['x']+ex)/2-h['c']*h['l']*math.sin(h['a']); my=(h['y']+ey)/2+h['c']*h['l']*math.cos(h['a'])
    pts=[(((1-t)**2)*h['x']+2*(1-t)*t*mx+t*t*ex,((1-t)**2)*h['y']+2*(1-t)*t*my+t*t*ey) for t in np.linspace(0,1,7)]
    for k in range(6): d.line([pts[k],pts[k+1]],fill=tuple(h['col'])+(int(255*h['al']*(1-k/9)),),width=max(1,round(h['w']*(1-k/8))))
im.alpha_composite(lay); im.convert('RGB').resize((im.width//2,im.height//2)).save('chk_fios.jpg')
