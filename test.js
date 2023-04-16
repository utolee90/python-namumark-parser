// 원본 : 사용자:하늘/custom-navbar.js
// 수정 : 사용자:Utolee90
// custom-navbar-data 불러오기 -> navBarData 형식으로 값이 호출됨.
var dataPageName = "User:" + mw.config.get().wgUserName + "/custom-navbar-data.json"; // custom-navbar-data 파일이름

// csv 파일 RAW 데이터를 얻기 위해서 필요
function getRaw(title) {
    var raw;
    $.ajax({
        async: false,
        url: location.origin + mw.util.getUrl(title || mw.title, { action: 'raw' }),
        success: function (data) { raw = data; }
    });
    return raw;
}

console.log(getRaw(dataPageName));
// 아이템 추가
var libreNavLogin = {};

libreNavLogin.navBarData = JSON.parse(getRaw(dataPageName));
// 제거할 메뉴 : 메뉴 타이틀명
libreNavLogin.titleMap = {
    "dropRC": "위키의 최근 바뀐 목록 [alt-shift-r]",  // 최근 바뀜 메뉴
    "dropRandom": "무작위로 선택된 문서 불러오기 [alt-shift-x]", // 임의 문서 메뉴
    "dropMap": "https://maps.librewiki.net/", // 리브레 맵스 메뉴
    "dropBoard": "게시판", // 게시판 메뉴(드롭다운)
    "dropWikiBoard": "https://bbs.librewiki.net/", // 위키 게시판(하위 링크)
    "dropFreeBoard": "https://bbs.librewiki.net/freeboard", //자유 게시판(하위 링크)
    "dropTools": "도구", // 도구(드롭다운)
    "dropSpecial": "특수:특수문서", // 특수문서(하위링크)
    "dropUpload": "특수:올리기", // 업로드(하위 링크)
    "dropHelp": "도움말", // 도움말(드롭다운)
    "dropSummary": "리브레_위키:도움말", // 위키 도움말(하위 링크)
    "dropSyntax": "도움말:위키_문법", // 위키 문법(하위 링크)
    "dropTex": "도움말:TeX_문법", // TeX 문법(하위 링크)
    "dropMenuMy": "내 사용자 문서 [alt-shift-.]", // 내 사용자 문서
    "dropMenuEcho": "당신의 알림", // 알림 (사용자 메뉴)
    "dropMenuContribution": "내 기여 목록 [alt-shift-y]", // 내 기여 목록
    "dropMenuTalk": "내 토론 문서 [alt-shift-n]", // 내 토론 문서
    "dropMenuWatch": "주시문서에 대한 바뀜 목록 [alt-shift-l]", // 주시문서 목록
    "dropMenuSettings": "사용자 환경 설정", // 환경 설정
};

libreNavLogin.titleMap2 = {
    "RC": "위키의 최근 바뀐 목록 [alt-shift-r]",  // 최근 바뀜 메뉴
    "random": "무작위로 선택된 문서 불러오기 [alt-shift-x]", // 임의 문서 메뉴
    "map": "https://maps.librewiki.net/", // 리브레 맵스 메뉴
    "board": "게시판", // 게시판 메뉴(드롭다운)
    "wikiBoard": "https://bbs.librewiki.net/", // 위키 게시판(하위 링크)
    "freeBoard": "https://bbs.librewiki.net/freeboard", //자유 게시판(하위 링크)
    "tools": "도구", // 도구(드롭다운)
    "special": "특수:특수문서", // 특수문서(하위링크)
    "upload": "특수:올리기", // 업로드(하위 링크)
    "help": "도움말", // 도움말(드롭다운)
    "summary": "리브레_위키:도움말", // 위키 도움말(하위 링크)
    "syntax": "도움말:위키_문법", // 위키 문법(하위 링크)
    "Tex": "도움말:TeX_문법", // TeX 문법(하위 링크)
    "menuMy": "내 사용자 문서 [alt-shift-.]", // 내 사용자 문서
    "menuEcho": "당신의 알림", // 알림 (사용자 메뉴)
    "menuContribution": "내 기여 목록 [alt-shift-y]", // 내 기여 목록
    "menuTalk": "내 토론 문서 [alt-shift-n]", // 내 토론 문서
    "menuWatch": "주시문서에 대한 바뀜 목록 [alt-shift-l]", // 주시문서 목록
    "menuSettings": "사용자 환경 설정", // 환경 설정
};

//
libreNavLogin.createItem = function(icon, title, url, desc, isMenu=false) {
  var a = document.createElement('a'); // 링크 추가
  var iconHTML = document.createElement('span'); // icon 추가
  iconHTML.className = "fa "+icon;
  iconHTML.style.color = isMenu? 'inherit' :'#373a3c'; // 색상 변경
  iconHTML.style.fontSize = isMenu? 'inherit' : '0.9em'; // 사이즈 변경
  iconHTML.style.padding = '0.2em 0'; // 아이콘 여백 조정
  a.className = isMenu? "nav-link" : "dropdown-item",
    a.href = url,
    a.innerHTML = title,
    a.title = desc;
  // icon이 빈 값이 아닐 때 아이콘 추가 
  if (icon != '' && icon !=undefined) {
     a.prepend(iconHTML); 
  }
  return a;
};
// 사용자 
libreNavLogin.addNavItem = function(icon, name, url, desc) {
  var node = this.createItem(icon, name, url, desc); // 아이템 생성
  document.getElementsByClassName('dropdown-divider')[0].before(node);
};
// 신규 아이콘 추가 함수
libreNavLogin.addMenuItem = function(icon, name, url, desc, part) {
  var node = this.createItem(icon, name, url, desc, part === 'new'); // 아이템 생성
  switch(part) {
    case 'user' : { // 사용자 메뉴
       document.getElementsByClassName('dropdown-divider')[0].before(node);
       break;
    }
    case 'board': { // 게시판
        document.querySelector('.navbar-fixed-top a.nav-link[title="게시판"]').nextElementSibling.appendChild(node)
        break;
     }
    case 'tools': { // 도구
       document.querySelector('.navbar-fixed-top a.nav-link[title="도구"]').nextElementSibling.appendChild(node)
       break;
    }
    case 'help': { // 도움말
      document.querySelector('.navbar-fixed-top a.nav-link[title="도움말"]').nextElementSibling.appendChild(node)
      break;
    }
    case 'new': { // 신규 메뉴
      var menuLi = document.createElement('li'); 
      menuLi.classList.add('nav-item');
      menuLi.appendChild(node);
      document.querySelector('.navbar-fixed-top ul.navbar-nav').appendChild(menuLi);
      break;
    }
    case 'dropdown': { // 신규 드롭다운. 지원 예정.
    }
  }
};
// 기존 아이콘 제거 함수
libreNavLogin.removeItem = function(name) {
  var Selector = '.navbar-fixed-top a[title="' + name + '"]'; // 타이틀 이름을 가진 링크. 사이드이펙트 방지를 위해 navbar-fixed-top 속성 추가. 
  document.querySelector(Selector).remove();
};
libreNavLogin.setNavItems = function() {
  // 사용자 메뉴 버튼에 추가.
  // for (const item of this.navBarData.newNavItems) {
  //   this.addNavItem(item[0], item[1], item[2], item[3]);
  // }
  // 드롭다운 링크 추가 - 게시판
  // for (const item of this.navBarData.addBoard) {
  //   this.addMenuItem(item[0], item[1], item[2], item[3], 'board');
  //}
  // 드롭다운 링크 추가 - 도구
  // for (const item of this.navBarData.addTools) {
  //   this.addMenuItem(item[0], item[1], item[2], item[3], 'tools');
  // }
  // 드롭다운 링크 추가 - 도움말
   // for (const item of this.navBarData.addHelp) {
   //  this.addMenuItem(item[0], item[1], item[2], item[3], 'help');
  // }
  // 드롭다운 링크 추가 - 내비게이션 바
   // for (const item of this.navBarData.addNew) {
   //   this.addMenuItem(item[0], item[1], item[2], item[3], 'new');
  // }
 // 메뉴 추가 - navBarData.addList 오브젝트 사용
   for (typical in this.navBarData.addList) {
        for (const item of this.navBarData.addList[typical]) {
            this.addMenuItem(item[0], item[1], item[2], item[3], typical);
        }
   }

  // 기존에 있는 메뉴 제거하는 과정
  for (const key in this.titleMap2) { // titleMap2에서 key값 추출
     if (this.navBarData.dropList.indexOf(key)>-1) {
        this.removeItem(this.titleMap2[key]); 
     }
  }
  // 메뉴 앞의 알림버튼 지우기 여부
  if (this.navBarData.dropList.indexOf('echo')>-1) {
      document.querySelector('#pt-notifications-notice').remove();
  }
  // 로그아웃 버튼 지우기 여부
  if(this.navBarData.dropList.indexOf('logout')>-1) {
    document.querySelector('.hide-logout.logout-btn').remove();
  }
};

// 아이템 추가
libreNavLogin.setNavItems();

// 랜덤 한자 출력 - 사:하늘/custom-navbar.js 참조
var api_params = {
  action: 'query',
  list: 'categorymembers',
  cmtitle: '분류:한자/문자',
  cmlimit: 'max',
  format: 'json',
  cmtype: 'page'
};

function navItem() {
  this.root = document.createElement('li');
  this.root.id = 'hanja-random';
  this.root.className = "nav-item";
  document.querySelector('.nav.navbar-nav').append(this.root);

  function link() {
    var span = () => { return document.createElement('span'); };
    var a = document.createElement('a');

    this.root = a;
    this.root.className = "nav-link";
    this.root.title = "한자 랜덤문서";

    this.icon = span();
    this.icon.style.fontWeight = "600",
      this.icon.innerText = '漢';

    this.title = span();
    this.title.className = "hide-title",
    this.title.innerText = ' 한자 랜덤';

    this.root.append(this.icon);
    this.root.append(this.title);

    var isloaded = false;
    this.root.onmouseenter = function() {
      if (isloaded === false) {
        var link = document.querySelector('#hanja-random a');
    	new mw.Api().get(api_params).done(function(data) {
          var pages = data.query.categorymembers;
          var randomTitle = pages[Math.floor(Math.random() * pages.length)].title;
          link.href = "/wiki/" + randomTitle;
          isloaded = true;
          console.log(randomTitle);
        });
      }
    };
  }
  this.link = new link();
  this.root.append(this.link.root);
}
// 한자 사전 아이템 추가 - 사:하늘 소스 활용. 템플릿만으로는 처리 불가능.
// new navItem();
