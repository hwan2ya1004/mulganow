/* 
 * 작성자 : 천승환
 * 작성일 : 2014-10-06
 * 설명   : 품목별 가격정보
 */

$(document).ready(function(){

	var title = '한국소비자원 참가격 > '+$('#hid_goodClassName').val()+' 가격정보';
	
	// 2024.04.12 웹접근성 버튼 포커스 지정 및 타이틀 추가by 이승진
	if($("#orderBy").val() == "Asc"){
		$("#orderByAsc").focus();
		$("#orderByAsc").attr('title','최저가순 선택됨');
	} else if($("#orderBy").val() == "Desc") {
		$("#orderByDesc").focus();
		$("#orderByDesc").attr('title','최고가순 선택됨');
	}
	
	var goodSmlcNm = $("#goodSmlclsCode option[value='"+$('#hid_goodSmlclsCode').val()+"']").text();
	if(goodSmlcNm != '') {
		title += (' - '+goodSmlcNm);
	}
	
	if ($("#entpTypeTab").val() == "LM") {
		title += ' - 대형마트';
	} else if ($("#entpTypeTab").val() == "DP") {
		title += ' - 백화점';
	} else if ($("#entpTypeTab").val() == "SM") {
		title += ' - 슈퍼마켓';
	} else if ($("#entpTypeTab").val() == "TR") {
		title += ' - 전통시장';
	} else if ($("#entpTypeTab").val() == "CS") {
		title += ' - 편의점';
	} else {
		title += ' - 전체';
	}
	
	$(document).attr("title",title);
	
	// 조사연도 설정
	$.ajax({
		type:"POST",
		url: "/tprice/portal/dailynecessitypriceinfo/priceiteminfo/getInspectYear.do",
		data: "",
		dataType:"json",
		success:function(data){
			var codeData = data.json;
			$.each(codeData, function(i){
				if(codeData[i].CODE == $("#hid_inspectYear").val()){
					$("#inspectYear").append("<option value='" + codeData[i].CODE + "' selected='selected' >" + codeData[i].CODE_NAME + "</option>");
				}
				else{
					$("#inspectYear").append("<option value='" + codeData[i].CODE + "'>" + codeData[i].CODE_NAME + "</option>");
				}
			});
			
			// 조사월 조회 호출
			fn_getInspectMonth($("#inspectYear").val(), fn_getInspectDay);
		},
		failure:function(data){}
	});

	// 업체목록 설정
	fn_setEntpList($("#hid_entpTypeCode").val(), $("#hid_entpAreaCode").val(), $("#hid_entpId").val());
	
	// 상품명 설정
	if($("#hid_goodId").val() == ""){
		fn_getGoodCodeList($("#goodSmlclsCode").val(), "");
	}else{
		fn_getGoodCodeList($("#hid_goodSmlclsCode").val(), $("#hid_goodId").val());
	}
	
	// 조사연도 변경
	$("#inspectYear").change(function(){
		// 조사월 조회 호출
		fn_getInspectMonth($(this).val(), fn_getInspectDay);
	});
	
	// 조사월 변경
	$("#inspectMonth").change(function(){
		// 조사일 조회 호출
		fn_getInspectDay($("#inspectYear").val(), $(this).val());
	});
	
	// 업태 체크박스
	$("#chk_entpAll").click(function(){
		$("[name=chk_entpType]").prop("checked", $(this).is(":checked"));
	});
	var entpTypeArr = new Array();
	if($("#hid_entpTypeCode").val() != ""){
		entpTypeArr = $("#hid_entpTypeCode").val().split(",");
	}
	
	$("[name=chk_entpType]").click(function(){
		/* 2016.07.29 수정 : 전체 체크박스 숨김
		var chkAll = true;
		var chkCnt = 0;
		
		$("[name=chk_entpType]").each(function(i){
			
			   if($(this).is(":checked") == false){
				chkAll = false;
				chkCnt++;
			}
			
		});
		
		* 기본 체크를 삭제하여 얼럿창 표시 누락시킴
		if(chkCnt == $("[name=chk_entpType]").length){
			alert("업태는 하나 이상 선택 해야 합니다."); 
		}
		
		// 전체 체크박스 체크 상태 변경
		$("#chk_entpAll").prop("checked", chkAll);
		*/
		
		entpTypeArr = new Array(); //초기화
		// 각 업태의 체크박스 확인
		$("[name=chk_entpType]:checked").each(function(){
			entpTypeArr.push($(this).val());
		});
		
		$("#hid_entpTypeCode").val(entpTypeArr.join(","));
		fn_setEntpList($("#hid_entpTypeCode").val(), $("#entpAreaCode").val(), "");
	});
	
	// 지역 변경
	$("#entpAreaCode").change(function(){
		fn_setEntpList($("#hid_entpTypeCode").val(), $(this).val(), "");
	});
	
	// 품목 변경
	$("#goodSmlclsCode").change(function(){
		if($(this).val() == ""){
			$("#goodId option").each(function(){
				$(this).remove();
			});
			$("#goodId").append("<option value=''>전체</option>");
		}
		else{
			fn_getGoodCodeList($(this).val(), "");
		}
	});
	
	// 최근본상품에 추가
	setTimeout(function(){			//가격정보를 조회후에 가져올 수 있으므로 setTime으로 정보 취득
		var goodId = $("#goodId").val();
		var goodClassCode =  $("#hid_goodClassCode").val();
		var goodImg = "";
		
		// 최근본상품 이미지
		for(var j=0; j<goodInfoList.length; j++){
			if(goodId == goodInfoList[j][0]){
				goodImg = goodInfoList[j][6];
			}
		}
		
		if(goodId != null && goodId != "" && entpTypeArr.length != 0){
			fn_setCookie("latestItem"
					, $("#goodId option:selected").val()   	// 상품 ID
					, $("#goodId option:selected").text()  	// 상품 명
					, goodImg  							   	// 상품 이미지
					, $("#hid_avgPrice_"+goodId).val()     	// 상품 평균가
					, $("#entpId").val() 				   	// 판매업체 ID
					, "" 								   	// 판매업체 명
					, "" 									// 상품가격
					, $("#inspectYear").val()   			// 조회연도
					, $("#inspectMonth").val() 				// 조회월
					, $("#inspectDay").val()   				// 조회일
					, $("#entpAreaCode").val()   			// 조회지역
					, $("#entpId").val()   					// 조회업체
					, $("#goodSmlclsCode").val()   			// 조회품목
					, goodId   								// 조회상품
					, ($("#td_minPrice_"+goodId).text()).replace(/,/g, "") // 최저가격
					, goodClassCode
					, entpTypeArr.join("!@") 				// 조회업태 (쿠키를 쉼표 스플릿으로 생성하므로 특수문자 사용)
					);
		}
	},300);

	// 검색버튼
	$("#search_btn").click(function(){
		
		var entpTypeTab = new Array();
		var texton ="";
		$("#tab_menu ul li").each(function(){
			texton = $(this).attr("class");
			if(texton == 'on'){
				entpTypeTab.push($(this).find("span a").attr("href").substr(6));
			}
		});
		
		if(entpTypeArr.length == 0){
			alert("업태는 하나 이상 선택 해야 합니다.");
			$("#schForm").attr("onsubmit", "return false");
			return;
		}
		
//		if( $('#goodId').val() == '' ) {
//			alert("상품을 선택하세요.");
//			$('#goodId').focus();
//			$("#schForm").attr("onsubmit", "return false");
//			return;
//		}
		
		$("#schForm").append(makeField("searchType", "btnSearch"));
		$("#schForm").append(makeField("entpTypeTab", entpTypeTab));
		$("#schForm").append(makeField("entpTypeArr", entpTypeArr));
		$("#schForm").append(makeField("goodClassCode", $("#hid_goodClassCode").val()));
		$("#schForm").attr("onsubmit", "return true");
		$("#schForm").attr("action", "/tprice/portal/dailynecessitypriceinfo/priceiteminfo/getPriceItemInfoList.do")
		.submit();
	});

	// 탭
	$("#tab_menu ul li span a").click(function(){
		var entpTypeTab = new Array();

		entpTypeTab.push($(this).attr("href").substr(6));
		
		$("#schForm").append(makeField("searchType", "tabSearch"));
		$("#schForm").append(makeField("entpTypeTab", entpTypeTab));
		$("#schForm").append(makeField("entpTypeArr", entpTypeArr));
		$("#schForm").append(makeField("goodClassCode", $("#hid_goodClassCode").val()));
		
		$("#schForm")
			.attr("action", "/tprice/portal/dailynecessitypriceinfo/priceiteminfo/getPriceItemInfoList.do")
			.submit();
	});

	$("#btn_popClose").click(function(){
		targetIcon.focus();
		$(".pop_chart").bPopup().close();
	});
	
	// 차트보기
	$("td").on("click", "button[name='viewChart']", function(){
		targetIcon = $(this);
		
		$('.pop_chart').bPopup({});
		
		var chartTitle = $(this).siblings("input[name='entpName']").val();
		var goodName = $(this).siblings("input[name='goodName']").val();
		var goodPriceArr = new Array();
		var categories = ["1년전","6개월전","1개월전","2주전","현재"];
		var tablesummary = chartTitle + " " + goodName + " 의 1년전, 6개월전, 1개월전, 2주전, 현재 가격 변동 안내";
		
		var strHtml = "<tr><th scope='row'>"+goodName+"</th>";
		
		for(var i=1; i<=5; i++){
			if($(this).siblings("input[name='goodPrice"+i+"']").val() != ""){
				var tmpPrice = Number($(this).siblings("input[name='goodPrice"+i+"']").val(), 10);
				
				goodPriceArr.push(tmpPrice);
				strHtml += "<td>" + $.number(tmpPrice) + "</td>";
			}
			else{
				goodPriceArr.push(null);
				strHtml += "<td></td>";
			}
		}
		
		strHtml += "</tr>";
		
		$("#tb_summary").attr("summary", tablesummary);
		$("#tbd_data").html(strHtml);
		
		$('.layer_graph').highcharts({
			credits: {
				text:"",
				href:""
			},
			tooltip : {
				enabled : false
			},
			title: {
				text: chartTitle
				//x: -20 //center
			},
			xAxis: {
				categories: categories
			},
			plotOptions: {
				series: {
					animation: {
						duration: 1500 /// 라인이 그려지는 속도를느리게 함
					}
				}
			},
			exporting: {
				enabled:false
			},
			yAxis: {
				floor: 0,
				//alternateGridColor: '#FDFFD5',
				labels: {
					format: '{value}원'
				},
				title: {
					text: ' '
				},
				plotLines: [{
					value: 1,
					width: 2,
					color: '#808080'
				}]
			},
			series: [{
				name: goodName,
				data: goodPriceArr
			}]
		});
		
		$(".pop_chart h2").focus();
	});

	// 정렬 변경
	$("#orderByAsc, #orderByDesc").click(function(){
		var order = $(this).attr("id").substring(7);
		var entpTypeArr = new Array();
		var entpTypeTab = new Array();
		// 페이지 초기화
		$("[name=pageNo]").val("1");
	
		var texton ="";
		$("#tab_menu ul li").each(function(){
			texton = $(this).attr("class");
			if(texton == 'on'){
//				entpTypeTab.push($("#tab_menu ul li span a ").attr("href").substr(6));
				entpTypeTab.push($(this).find("span a").attr("href").substr(6));
			}
		});
		
		
		$("[name=chk_entpType]:checked").each(function(){
			entpTypeArr.push($(this).val());
		});
		
		$("#schForm").append(makeField("searchType", "tabSearch"));
		$("#schForm").append(makeField("entpTypeTab", entpTypeTab));
		$("#schForm").append(makeField("entpTypeArr", entpTypeArr));
		$("#schForm").append(makeField("goodClassCode", $("#hid_goodClassCode").val()));
		$("#orderBy").val(order);
		
		$("#schForm")
			.attr("action", "/tprice/portal/dailynecessitypriceinfo/priceiteminfo/getPriceItemInfoList.do")
			.submit();
	});

	// 장바구니 버튼
	$("td").on("click", "button[name='btn_addCart']", function(){
		var imgSrc = $(this).find("img").attr("src");
		var cutIdx = imgSrc.indexOf("ico_cart");
		
		var goodId = $(this).siblings("input[name='hid_cartGoodId']").val();
		var goodClassCode =  $("#hid_goodClassCode").val();
		
		if(imgSrc.substring(cutIdx) == "ico_cart.png"){
			fn_setCookie("cartItem"
					, $(this).siblings("input[name='hid_cartGoodId']").val()   // 상품 ID
					, $(this).siblings("input[name='hid_cartGoodName']").val() // 상품 명
					, $("#hid_file_"+goodId).val()  // 상품 이미지
					, $("#hid_avgPrice_"+goodId).val()     // 상품 평균가
					, $(this).siblings("input[name='hid_cartEntpId']").val()       // 판매업체 ID
					, $(this).siblings("input[name='hid_entpName']").val()     // 판매업체 명
					, $(this).siblings("input[name='hid_goodPrice']").val()     // 상품가격
					, "" // 조회연도
					, "" // 조회월
					, "" // 조회일
					, ""   // 조회지역
					, ""   // 조회업체
					, ""   // 조회품목
					, ""   // 조회상품
					, ""   // 최저가격
					,goodClassCode
					);
		}
		else{
			fn_delCookie("cartItem", $(this).siblings("input[name='hid_cartGoodId']").val(), "");
		}
	});
	
	// 관심품목 버튼
	$("td").on("click", "button[name='btn_addInterestItem']", function(){
		var imgSrc = $(this).find("img").attr("src");
		var cutIdx = imgSrc.indexOf("ico_fav");
		
		if(imgSrc.substring(cutIdx) == "ico_fav.png"){
			var goodId = $(this).siblings("input[name='hid_cartGoodId']").val();
			var inspectYear = $("#inspectYear option:selected").val();
			var inspectMonth = $("#inspectMonth option:selected").val();
			var inspectDay = $("#inspectDay option:selected").val();
			var entpAreaCode = $("#entpAreaCode option:selected").val();
			var goodSmlclsCode = $(this).siblings("input[name='hid_smlclsCode']").val();
			var goodClassCode =  $("#hid_goodClassCode").val();
			
			fn_setCookie("interestItem"
					, goodId   // 상품 ID
					, $(this).siblings("input[name='hid_cartGoodName']").val() // 상품 명
					, $("#hid_file_"+goodId).val()  // 상품 이미지
					, $("#hid_avgPrice_"+goodId).val()     // 상품 평균가
					, $(this).siblings("input[name='hid_cartEntpId']").val()       // 판매업체 ID
					, $(this).siblings("input[name='hid_entpName']").val()     // 판매업체 명
					, $(this).siblings("input[name='hid_goodPrice']").val()     // 상품가격
					//, inspectYear // 조회연도
					//, inspectMonth // 조회월
					//, inspectDay // 조회일
					, inspectYear // 조회연도
					, inspectMonth // 조회월
					, inspectDay // 조회일
					, entpAreaCode   // 조회지역
					, entpAreaCode   // 조회업체
					, goodSmlclsCode   // 조회품목
					, ""   // 조회상품
					, ($("#td_minPrice_"+goodId).text()).replace(/,/g, "") // 최저가격
					, goodClassCode
					);
		}
		else{
			fn_delCookie("interestItem", $(this).siblings("input[name='hid_cartGoodId']").val(), $(this).siblings("input[name='hid_cartEntpId']").val());
		}
	});
	
	// 판매업체 위치(지도) 버튼
	$("td").on("click", "button[name='btnMap']", function(){
		targetIcon = $(this);
		var entpId = $(this).parent("td").parent("tr").find("input[name='hid_cartEntpId']").val();
		fn_bpopup("/tprice/portal/map/map.do?entpId="+entpId+"&serviceType=default", 850, 600, '판매업체 위치(지도)');
	});
	
	// 페이지당 보이는 건수 변경
	$("#btn_pageUnit").click(function(){
		$("#search_btn").trigger("click");
	});
	

	
	$("#goPublicApi").click(function(){
		var url = "https://www.data.go.kr/subMain.jsp#/L3B1YnIvdXNlL3ByaS9Jcm9zT3BlbkFwaURldGFpbC9vcGVuQXBpT" +
				"GlzdFBhZ2UkQF4wMTJtMSRAXnB1YmxpY0RhdGFQaz0zMDQzMzg1JEBeYnJtQ2Q9T0MwMDA" +
				"1JEBecmVxdWVzdENvdW50PTEwJEBeb3JnSW5kZXg9T1BFTkFQSQ==";
		window.open(url, "_blank");  
	});
	
});

/*
 * 설  명 : 맵 레이어 팝업 종료
 */
function fn_MapLayerClose(){
	var bPopup = $('#element_to_pop_up').bPopup();
	bPopup.close();
	
	$('#element_to_pop_up').html('');
	
	targetIcon.focus();
}


$(window).load(function(){
	var chkCnt = 0;
	
	// 최초 화면 로딩시 전체체크 박스 체크 여부
	$("[name=chk_entpType]").each(function(){
		if($(this).is(":checked")){
			chkCnt++;
		}
	});
	
	if($("[name=chk_entpType]").length == chkCnt){
		$("#chk_entpAll").prop("checked", true);
	}

	// 장바구니 버튼 이미지 반전
	fn_changeImg("cartItem", "", "");
	// 관심품목 버튼 이미지 반전
	fn_changeImg("interestItem", "", "");
});

//pagination 페이지 링크
function fn_gotoPage(page){
	var url = "/tprice/portal/dailynecessitypriceinfo/priceiteminfo/getPriceItemInfoList.do";

	var entpTypeArr = new Array();
	var entpTypeTab = new Array();
	var texton ="";
	$("#tab_menu ul li").each(function(){
		texton = $(this).attr("class");
		if(texton == 'on'){
//			entpTypeTab.push($("#tab_menu ul li span a ").attr("href").substr(6));
			entpTypeTab.push($(this).find("span a").attr("href").substr(6));
		}
	});
	
	$("[name=chk_entpType]:checked").each(function(){
		entpTypeArr.push($(this).val());
	});
	
	// 페이지 이동할대 검색조건 설정
	$("#sendFields").html(makeField("inspectYear", $("#inspectYear").val()));
	$("#sendFields").append(makeField("inspectMonth", $("#inspectMonth").val()));
	$("#sendFields").append(makeField("inspectDay", $("#inspectDay").val()));
	$("#sendFields").append(makeField("entpAreaCode", $("#entpAreaCode").val()));
	$("#sendFields").append(makeField("entpId", $("#entpId").val()));
	$("#sendFields").append(makeField("goodClassCode", $("#hid_goodClassCode").val()));
	$("#sendFields").append(makeField("goodSmlclsCode", $("#goodSmlclsCode").val()));
	$("#sendFields").append(makeField("goodId", $("#goodId").val()));
	$("#sendFields").append(makeField("searchType", "tabSearch"));
	$("#sendFields").append(makeField("entpTypeTab", entpTypeTab));
	$("#sendFields").append(makeField("entpTypeArr", entpTypeArr));
	$("#sendFields").append(makeField("pageUnit",$("#hid_pageUnit").val() ));
	
	gotoPageSend(page, url);
}

// 조사월 조회
function fn_getInspectMonth(inspectYear, callbackFn){
	$("#inspectMonth option").each(function(){
		$(this).remove();
	});
	
	$.ajax({
		type:"POST",
		url: "/tprice/portal/dailynecessitypriceinfo/priceiteminfo/getInspectMonth.do",
		data: "inspectYear="+inspectYear,
		dataType:"json",
		success:function(data){
			var codeData = data.json;
			$.each(codeData, function(i){
				if(codeData[i].CODE == $("#hid_inspectMonth").val()){
					$("#inspectMonth").append("<option value='" + codeData[i].CODE + "' selected='selected' >" + codeData[i].CODE_NAME + "</option>");
				}
				else{
					$("#inspectMonth").append("<option value='" + codeData[i].CODE + "'>" + codeData[i].CODE_NAME + "</option>");
				}
			});

			if( typeof callbackFn === "function" ) {
				// 조사일 조회 호출
				callbackFn(inspectYear, $("#inspectMonth").val());
			}
		},
		failure:function(data){}
	});
}

// 조사일 조회
function fn_getInspectDay(inspectYear, inspectMonth){
	$("#inspectDay option").each(function(){
		$(this).remove();
	});
	
	$.ajax({
		type:"POST",
		url: "/tprice/portal/dailynecessitypriceinfo/priceiteminfo/getInspectDay.do",
		data: "inspectYear="+inspectYear + "&inspectMonth="+inspectMonth,
		dataType:"json",
		success:function(data){
			var codeData = data.json;
			$.each(codeData, function(i){
				if(codeData[i].CODE == $("#hid_inspectDay").val()){
					$("#inspectDay").append("<option value='" + codeData[i].CODE + "' selected='selected' >" + codeData[i].CODE_NAME + "</option>");
				}
				else{
					$("#inspectDay").append("<option value='" + codeData[i].CODE + "'>" + codeData[i].CODE_NAME + "</option>");
				}
			});
		},
		failure:function(data){}
	});
}

// 업체명 조회
function fn_setEntpList(entpTypeCode, entpAreaCode, selVal){
	$("#entpId option").each(function(){
		$(this).remove();
	});
	$("#entpId").append("<option value=''>전체</option>");
	
	fn_getEntpList(entpTypeCode, entpAreaCode, "", "entpId", selVal);
}

// 품목별 상품 조회
function fn_getGoodCodeList(goodSmlclsCode, selVal){
	$("#goodId option").each(function(){
		$(this).remove();
	});
	$("#goodId").append("<option value=''>전체</option>");
	
	$.ajax({
		type:"POST",
		url: "/tprice/portal/dailynecessitypriceinfo/priceiteminfo/getGoodCodeList.do",
		data: "goodSmlclsCode="+goodSmlclsCode,
		dataType:"json",
		success:function(data){
			var codeData = data.json;
			$.each(codeData, function(i){
				if(codeData[i].CODE == selVal){
					$("#goodId").append("<option value='" + codeData[i].CODE + "' selected='selected' >" + codeData[i].CODE_NAME + "</option>");
					$('#hid_goodImgId').val(codeData[i].fileRgtnSeq);
				}
				else{
					$("#goodId").append("<option value='" + codeData[i].CODE + "'>" + codeData[i].CODE_NAME + "</option>");
				}
			});
		},
		failure:function(data){}
	});
}

//상품정보를 cookie에 저장
function fn_setCookie(cookieNm, goodId, goodNm, goodImg, goodAvgPrice, entpId
		, entpNm, goodPrice, schYear, schMonth, schDay, schArea, schEntp, schCls, schItem, minPrice, goodClassCode, entpTypeCode){
	var cookieVal = new Array();
	
	if($.cookie(cookieNm) != undefined){
		cookieVal = $.cookie(cookieNm).split(",");
		
		if(cookieNm == "cartItem"){

			// 쿠키 길이 오류로 인해 장바구니 2개로 제한
			if(cookieVal.length == 2){
				cookieVal.splice(0, 1);
				$.cookie(cookieNm, cookieVal.join(","), {path:'/',expires:30});
			}
			
			if(cookieVal.length == 20){
				alert("상품은 20개만 선택 가능 합니다.");
				return;
			}
			
			$.cookie(cookieNm, $.cookie(cookieNm) + ","
					+ goodId + ":" + goodNm + ":" + goodImg + ":" + goodAvgPrice + ":" + entpId + ":"
					+ entpNm + ":" + goodPrice + ":" + schYear + ":" + schMonth + ":" + schDay + ":"
					+ schArea + ":" + schEntp + ":" + schCls + ":" + schItem + ":" + minPrice + ":" 
					+ goodClassCode + ":" + entpTypeCode, {path:'/',expires:30});
		}
		else if(cookieNm == "interestItem"){
			if(cookieVal.length == 5){
				alert("관심품목은 5개만 선택 가능 합니다.");
				return;
			}

			$.cookie(cookieNm, $.cookie(cookieNm) + ","
					+ goodId + ":" + goodNm + ":" + goodImg + ":" + goodAvgPrice + ":" + entpId + ":"
					+ entpNm + ":" + goodPrice + ":" + schYear + ":" + schMonth + ":" + schDay + ":"
					+ schArea + ":" + schEntp + ":" + schCls + ":" + schItem + ":" + minPrice + ":" 
					+ goodClassCode + ":" + entpTypeCode, {path:'/',expires:30});
		}
		else if(cookieNm == "latestItem"){
			
			for(var i=0; i<cookieVal.length; i++){
				// 같은 상품이 있는지 확인
				if(goodId == cookieVal[i].split(":")[0]){
					fn_delCookie(cookieNm, goodId, entpId, "N");
				}
			}
			
			// 최근본상품의 수가 4개 이상이면 처음 본 상품 삭제
			if(cookieVal.length == 4){
				cookieVal.splice(0, 1);
				$.cookie(cookieNm, cookieVal.join(","), {path:'/',expires:30});
			}
			
			var newCookieVal = $.cookie(cookieNm);
			if(newCookieVal != undefined && $.trim(newCookieVal) != 'undefined'){
				newCookieVal += ",";
			}else{
				newCookieVal = "";
			}
			
			$.cookie(cookieNm, newCookieVal
					+ goodId + ":" + goodNm + ":" + goodImg + ":" + goodAvgPrice + ":" + entpId + ":"
					+ entpNm + ":" + goodPrice + ":" + schYear + ":" + schMonth + ":" + schDay + ":"
					+ schArea + ":" + schEntp + ":" + schCls + ":" + schItem + ":" + minPrice + ":" 
					+ goodClassCode + ":" + entpTypeCode, {path:'/',expires:30});
		}
	}
	else{
		$.cookie(cookieNm, goodId + ":" + goodNm + ":" + goodImg + ":" + goodAvgPrice + ":" + entpId + ":"
				+ entpNm + ":" + goodPrice + ":" + schYear + ":" + schMonth + ":" + schDay + ":"
				+ schArea + ":" + schEntp + ":" + schCls + ":" + schItem + ":" + minPrice + ":" 
				+ goodClassCode + ":" + entpTypeCode, {path:'/',expires:30});
	}
	
	// 장바구니, 관심품목 버튼 이미지 반전
	fn_changeImg(cookieNm, goodId, "");
	
	// 플로팅메뉴 관심품목 갱신
	fn_makeInterestGoodsHtml();
}

//상품정보를 cookie에서 삭제
function fn_delCookie(cookieNm, goodId, entpId, drawFlag){
	var cookieVal = new Array();
	var newCookieVal = "";
	var cookieValGoodId = "";
	var cookieValEntpId = "";
	
	cookieVal = $.cookie(cookieNm).split(",");
	
	if(cookieVal.length == 1){
		$.removeCookie(cookieNm, {path:'/',expires:30});
	}
	else{
		for(var i=0; i<cookieVal.length; i++){
			cookieValGoodId = cookieVal[i].split(":")[0];
			cookieValGoodNm = cookieVal[i].split(":")[1];
			cookieValGoodImg = cookieVal[i].split(":")[2];
			cookieValGoodAvgPrice = cookieVal[i].split(":")[3];
			cookieValEntpId = cookieVal[i].split(":")[4];
			cookieValEntpNm = cookieVal[i].split(":")[5];
			
			// 삭제 하고자 하는 상품과 다른 상품을 빼고 다시 cookie 로 만듬
			// 장바구니
			if(cookieNm == "cartItem"){
				if(goodId != cookieValGoodId){
					if(newCookieVal == ""){
						newCookieVal = cookieVal[i];
					}
					else{
						newCookieVal += "," + cookieVal[i];
					}
				}
			}
			// 관심품목
			else if(cookieNm == "interestItem"){
				if( !(goodId == cookieValGoodId && entpId == cookieValEntpId) ){
					if(newCookieVal == ""){
						newCookieVal = cookieVal[i];
					}
					else{
						newCookieVal += "," + cookieVal[i];
					}
				}
			}
			// 최근본상품
			else if(cookieNm == "latestItem"){
				if( !(goodId == cookieValGoodId && entpId == cookieValEntpId) ){
					if(newCookieVal == ""){
						newCookieVal = cookieVal[i];
					}
					else{
						newCookieVal += "," + cookieVal[i];
					}
				}
			}
		}
		$.cookie(cookieNm, newCookieVal, {path:'/',expires:30});
	}
	
	if(drawFlag != "N"){ //"N"일 시 html 반영안함
		// 장바구니, 관신품목 버튼 이미지 반전
		fn_changeImg(cookieNm, "", goodId, entpId);
		
		// 플로팅메뉴 관심품목 갱신
		fn_makeInterestGoodsHtml();
	}
}

// 장바구니, 관심품목 버튼 이미지 반전
function fn_changeImg(cookieNm, addGoodId, delGoodId, delEntpId){
	var cookieVal = new Array();
	var cookieValGoodId = "";
	var cookieValEntpId = "";
	var imgNm = "cart";
	var btnNm = "Cart";
	
	if(cookieNm == "interestItem"){
		imgNm = "fav";
		btnNm = "InterestItem";
	}
	
	if($.cookie(cookieNm) != undefined){
		cookieVal = $.cookie(cookieNm).split(",");
	}
	
	$("[name=btn_add" + btnNm + "Img]").each(function(){
		for(var i=0; i<cookieVal.length; i++){
			cookieValGoodId = cookieVal[i].split(":")[0];
			cookieValEntpId = cookieVal[i].split(":")[4];
			
			// 장바구니
			if(cookieNm == "cartItem"){
				// addGoodId 값이 있으면 버튼 클릭으로 장바구니에 추가
				if(addGoodId != "" && addGoodId == $(this).parent().siblings("input[name='hid_cartGoodId']").val()){
					$(this).attr("src", "/tprice/images/portal/contents/ico_" + imgNm + "_on.png");
					$(this).attr("title", "선택됨");
					$(this).parent().addClass('btnAddCart');
				}
				// addGoodId이 없으면 화면 로딩시 cookie에 있는 상품
				if(cookieValGoodId == $(this).parent().siblings("input[name='hid_cartGoodId']").val()){
					$(this).attr("src", "/tprice/images/portal/contents/ico_" + imgNm + "_on.png");
					$(this).attr("title", "선택됨");
					$(this).parent().addClass('btnAddCart');
				}
			}
			// 관심품목
			else if(cookieNm == "interestItem"){
				// addGoodId 값이 있으면 버튼 클릭으로 관심품목에 추가
//				if(addGoodId != "" && addGoodId == $(this).siblings("#hid_cartGoodId").val()){
//					$(this).find("img").attr("src", "/tprice/images/portal/contents/ico_" + imgNm + "_on.png");
//				}
				// addGoodId이 없으면 화면 로딩시 cookie에 있는 상품
				if(cookieValGoodId == $(this).parent().siblings("input[name='hid_cartGoodId']").val() && cookieValEntpId == $(this).parent().siblings("input[name='hid_cartEntpId']").val()){
					$(this).attr("src", "/tprice/images/portal/contents/ico_" + imgNm + "_on.png");
				}
			}
		}
		
		// 장바구니 상품 삭제
		if(cookieNm == "cartItem"){
			if(delGoodId != "" && delGoodId == $(this).parent().siblings("input[name='hid_cartGoodId']").val()){
				$(this).attr("src", "/tprice/images/portal/contents/ico_" + imgNm + ".png");
				$(this).removeAttr("title");
				$(this).parent().removeClass('btnAddCart');
			}
		}
		// 관심품목 상품 삭제
		else if(cookieNm == "interestItem"){
			if(delGoodId != "" && delGoodId == $(this).parent().siblings("input[name='hid_cartGoodId']").val() && delEntpId == $(this).parent().siblings("input[name='hid_cartEntpId']").val()){
				$(this).attr("src", "/tprice/images/portal/contents/ico_" + imgNm + ".png");
			}
		}
	});
}

//selectbox의 전체 항목 삭제
function fn_delPageUnit(){
	$("#pageUnit option").each(function(){
		if($(this).val() == ""){
			$(this).remove();
		}
	});
}