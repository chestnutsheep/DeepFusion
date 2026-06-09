#!/usr/bin/env python3
"""Kondratiev Wave: Global vs China Composite (PCA-based)"""
import os, sys, warnings, requests, io
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
warnings.filterwarnings("ignore")

sys.path.insert(0, "/")
OUT = Path("/home/AI/output"); OUT.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.sans-serif": ["DejaVu Sans"], "axes.unicode_minus": False})

# Kill proxy for NBS/FRED
for k in ['HTTP_PROXY','HTTPS_PROXY','http_proxy','https_proxy']: os.environ.pop(k,None)

def fred(sid, start):
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"
    r = requests.get(url, timeout=30); r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text), parse_dates=[0])
    df.columns = ["date","value"]; df = df.dropna()
    df = df[pd.to_datetime(df["date"]) >= pd.Timestamp(start)]
    s = df.set_index("date")["value"].astype(float).sort_index()
    print(f"  FRED {sid}: {s.index[0].year}-{s.index[-1].year}")
    return s

def nbs(kw, ik, lb, freq="MM"):
    from DeepFusion.deep_fusion import _get_nbs_client as cl
    try:
        df = cl().search_and_fetch(kw, ik, start="1980", freq=freq)
        if df is None or df.empty: return None
        vc = [c for c in df.columns if c != "period"][0]
        df[vc] = pd.to_numeric(df[vc], errors="coerce"); df = df.dropna(subset=[vc])
        y = df.groupby([str(p)[:4] for p in df["period"]])[vc].mean()
        s = pd.Series(y.values.astype(float), index=pd.to_numeric(y.index))
        print(f"  {lb}: {int(s.index[0])}-{int(s.index[-1])}"); return s
    except Exception as e:
        print(f"  {lb}: {e}"); return None

def hp(s, lam=100):
    orig = s.dropna(); vals = orig.values; n = len(vals)
    if n<5: return pd.Series(np.zeros(n), index=orig.index)
    I = np.eye(n); D = np.zeros((n-2,n))
    for i in range(n-2): D[i,i]=1; D[i,i+1]=-2; D[i,i+2]=1
    t = np.linalg.solve(I+lam*D.T@D, vals)
    return pd.Series(vals-t, index=orig.index)

print("=== Data ===")
cpi = fred("CPIAUCSL","1913-01-01")
gdp = fred("GDPC1","1947-01-01")
oil = fred("MCOILWTICO","1986-01-01")

all_nbs = {}
for kw,ik,lb in [("工业生产者出厂价格指数","上年同月","PPI"),("生产资料","上年同月","PPI_Cap"),
    ("发电量","","Power"),("粗钢","","Steel"),("水泥","","Cement"),
    ("货物周转量","","Freight"),("货物进出口总额","","Trade"),("货币供应量","","M2")]:
    s=nbs(kw,ik,lb); 
    if s is not None: all_nbs[lb]=s
for kw,ik,lb in [("软件业务收入","收入","IT"),("新能源汽车","产量","NEV"),("集成电路","产量","IC")]:
    s=nbs(kw,ik,lb); 
    if s is not None: all_nbs[lb]=s

proc = {}
for lb,s in all_nbs.items():
    if "PPI" in lb: proc[lb]=np.log((s/100.0).cumprod()*100).clip(lower=-10)
    else: proc[lb]=np.log(s.clip(lower=1e-6))

hr = {lb:hp(s) for lb,s in proc.items() if len(s)>=10}
long_k = [k for k in hr if k not in ("IT","NEV")]
c = sorted(set.intersection(*[set(hr[k].index.astype(int)) for k in long_k]))
c = [y for y in c if 1995<=y<=2024]
X = pd.DataFrame({k:pd.Series(hr[k].values,index=hr[k].index) for k in long_k}).reindex(c).dropna(axis=1)
Xs = StandardScaler().fit_transform(X.values)
pca = PCA(n_components=2)
PCs = pca.fit_transform(Xs)
ev = pca.explained_variance_ratio_
print(f"\nPCA: PC1={ev[0]:.2%} PC2={ev[1]:.2%} | {c[0]}-{c[-1]}")

cf = pd.Series(PCs[:,0], index=c)
c2 = pd.Series(PCs[:,1], index=c) if PCs.shape[1]>1 else None

# Global + HP
gdp_y = gdp.resample("YE").mean(); gdp_y.index=gdp_y.index.year
oil_y = oil.resample("YE").mean(); oil_y.index=oil_y.index.year
from scipy.signal import butter, sosfiltfilt
def cf_bp(s,lo=30,hi=60):
    if len(s)<30: return hp(s)
    sos=butter(4,[2/hi,2/lo],btype="band",output="sos",fs=1.); v=s.values-np.nanmean(s.values)
    return pd.Series(sosfiltfilt(sos,np.nan_to_num(v)),index=s.index)
glo = pd.DataFrame({"g":cf_bp(np.log(gdp_y.dropna())),"o":cf_bp(np.log(oil_y.dropna()))}).mean(axis=1)
glo = (glo-glo.mean())/glo.std()
ch = hp(cf); ch = (ch-ch.mean())/ch.std()

fig,ax = plt.subplots(4,1,figsize=(16,16),sharex=True)
ax[0].plot(c,cf,"k-",lw=2.5,label=f"PC1 ({ev[0]:.0%})")
if c2 is not None: ax[0].plot(c,c2,"r--",lw=2,label=f"PC2 ({ev[1]:.0%})")
ax[0].axhline(0,color="gray",lw=.5,ls="--"); ax[0].legend(fontsize=8); ax[0].grid(alpha=.3)
ax[0].set_title("A: PCA PC1+PC2")

old_k = [k for k in long_k if k in ("PPI","PPI_Cap","Steel","Cement","Freight","Power")]
if len(old_k)>=2:
    Xo = X[[k for k in X.columns if k in old_k]].dropna()
    if len(Xo)>5:
        pco = PCA(n_components=1).fit_transform(StandardScaler().fit_transform(Xo.values))
        so = (pd.Series(pco.flatten(),index=Xo.index)-pd.Series(pco.flatten(),index=Xo.index).mean())/pd.Series(pco.flatten(),index=Xo.index).std()
        ax[1].plot(so.index,so.values,"b-",lw=2,label="Old Eco")
new_k = [k for k in hr if k in ("IT","NEV","IC")]
if len(new_k)>=2:
    nc = sorted(set.intersection(*[set(hr[k].index.astype(int)) for k in new_k]))
    nc = [y for y in nc if 2017<=y<=2024]
    if len(nc)>=3:
        Xn = pd.DataFrame({k:pd.Series(hr[k].values,index=hr[k].index) for k in new_k}).reindex(nc).dropna()
        if len(Xn)>3:
            pcn = PCA(n_components=1).fit_transform(StandardScaler().fit_transform(Xn.values))
            sn = (pd.Series(pcn.flatten(),index=nc)-pd.Series(pcn.flatten(),index=nc).mean())/pd.Series(pcn.flatten(),index=nc).std()
            ax[1].plot(nc,sn,"g-",lw=2,label="New Eco")
ax[1].axhline(0,color="gray",lw=.5,ls="--"); ax[1].legend(fontsize=8); ax[1].grid(alpha=.3)
ax[1].set_title("B: Old vs New Economy")

ax[2].plot(glo.index,glo.values,"#d2991d",lw=2,label="Global")
ax[2].plot(c,(cf-cf.mean())/cf.std(),"k-",lw=2,label="China")
ax[2].axhline(0,color="gray",lw=.5,ls="--"); ax[2].legend(fontsize=8); ax[2].grid(alpha=.3)
ax[2].set_title("C: Global vs China")

ax[3].plot(ch.index,ch.values,"k-",lw=2,label="China HP(100)")
if c2 is not None: ax[3].plot(c,(c2-c2.mean())/c2.std(),"r--",lw=1.5,alpha=.7,label="PC2 HP")
ax[3].axhline(0,color="gray",lw=.5,ls="--"); ax[3].legend(fontsize=8); ax[3].grid(alpha=.3)
ax[3].set_title("D: Medium Cycle (HP)"); ax[3].set_xlabel("Year")
fig.tight_layout(); fig.savefig(OUT/"kondratiev_enhanced.png",dpi=150)
print(f"\n  Saved {OUT/'kondratiev_enhanced.png'}")

lg=glo.dropna().iloc[-1]; lc=ch.dropna().iloc[-1] if len(ch.dropna())>0 else 0
def ph(v):
    return "Boom" if v>.5 else ("Recovery" if v>0 else ("Recession" if v>-.5 else "Depression"))
rpt=f"""# Kondratiev Enhanced
PCA: PC1={ev[0]:.2%} PC2={ev[1]:.2%} | {c[0]}-{c[-1]}
Series: {list(X.columns)}
Global: {ph(lg)}(z={lg:.3f}) China HP: {ph(lc)}(z={lc:.3f})
"""
if ev[1]>.15: rpt+=f"PC2~{ev[1]:.0%} may reflect Kuznets cycle\n"
(OUT/"report_enhanced.md").write_text(rpt,encoding="utf-8")
print(f"  Saved {OUT/'report_enhanced.md'}\n=== Done ===")
