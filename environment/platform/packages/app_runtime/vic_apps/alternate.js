/* Meridian workspace: command launcher + right-hand navigation + adjustable density.
   All domain operations stay with the native application's own event handlers. */
(() => {
  if (document.getElementById('meridian-shell')) return;
  document.documentElement.dataset.environment = 'meridian';
  if(location.pathname.startsWith('/native/music/'))document.documentElement.dataset.application='music';
  const shell=document.createElement('header');shell.id='meridian-shell';
  const brand=document.createElement('strong');brand.textContent='MERIDIAN / 工作空间';
  const menu=document.createElement('button');menu.textContent='应用导航';menu.setAttribute('aria-expanded','false');
  const search=document.createElement('button');search.textContent='查找功能  ⌘ K';
  const density=document.createElement('button');density.textContent='紧凑视图';
  shell.append(brand,search,density,menu);document.body.append(shell);
  const dialog=document.createElement('dialog');dialog.id='meridian-command';
  const input=document.createElement('input');input.placeholder='搜索应用中的功能';input.setAttribute('aria-label','搜索功能');
  const list=document.createElement('div'),close=document.createElement('button');close.textContent='关闭';close.onclick=()=>dialog.close();
  dialog.append(input,list,close);document.body.append(dialog);
  // Restrict to genuine navigation controls. No hidden controls or task answers.
  const selector='.product-nav, .sidebar, .side-bar, .iconbar, .news-header nav, .meridian-im-nav, .navigation, nav[aria-label], [data-testid="stSidebar"]';
  const markIM=()=>{const sidebar=document.querySelector('#__next .ant-layout')?.firstElementChild;const rail=sidebar?.firstElementChild;if(rail?.querySelector('[title="通讯录"]')){sidebar.classList.add('meridian-im-list');rail.classList.add('meridian-im-nav');}};
  new MutationObserver(markIM).observe(document.body,{childList:true,subtree:true});markIM();
  const navigations=()=>[...document.querySelectorAll(selector)].filter(n=>!shell.contains(n));
  const items=()=>navigations().flatMap(n=>[...n.querySelectorAll('button,a')]).filter((n,i,a)=>a.indexOf(n)===i&&!n.disabled&&(n.textContent.trim()||n.title||n.getAttribute('aria-label')));
  function render(){list.replaceChildren();const query=input.value.trim().toLocaleLowerCase();for(const target of items()){
    const label=target.textContent.trim()||target.title||target.getAttribute('aria-label');if(query&&!label.toLocaleLowerCase().includes(query))continue;
    const b=document.createElement('button');b.textContent=label;b.onclick=()=>{dialog.close();target.click();document.documentElement.classList.remove('meridian-nav-open');menu.setAttribute('aria-expanded','false');};list.append(b);
  }if(!list.children.length){const note=document.createElement('p');note.textContent='未找到功能，请使用应用导航或页面内工具。';list.append(note);}}
  search.onclick=()=>{input.value='';render();dialog.showModal();input.focus();};input.oninput=render;
  menu.onclick=()=>{const open=document.documentElement.classList.toggle('meridian-nav-open');menu.setAttribute('aria-expanded',String(open));};
  density.onclick=()=>{const dense=document.documentElement.classList.toggle('meridian-dense');density.textContent=dense?'舒展视图':'紧凑视图';};
  document.addEventListener('keydown',e=>{if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='k'){e.preventDefault();search.click();}if(e.key==='Escape'){document.documentElement.classList.remove('meridian-nav-open');menu.setAttribute('aria-expanded','false');}});
  document.addEventListener('click',e=>{if(navigations().some(n=>n.contains(e.target))&&e.target.closest('button,a')){document.documentElement.classList.remove('meridian-nav-open');menu.setAttribute('aria-expanded','false');}});
})();
