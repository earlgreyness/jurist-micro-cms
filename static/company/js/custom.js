/*
* Кастомные скрипты
*/

$(document).ready(function () {

  $('#form-blue, #form-popup, #form-lead').submit(function (event) {

    var input = document.createElement("input");
    input.setAttribute("type", "hidden");
    input.setAttribute("name", "source_url");
    input.setAttribute("value", document.location.href);
    $(this).append(input);

    element = $(this).find('#tel, #phone, #yourphone');

    if ( !element.inputmask("isComplete") ) {
      element.addClass('input-invalid');
      // element.removeClass
      event.preventDefault();
    }

  });

  // Открывает/закрывает модальное окно "Заказать звонок"
  $('#recall_top, #recall_bottom').click( function( e ) {
    e.preventDefault();

    $('#recall_bg').css( 'display', 'block' );
    $('#recall').css( 'display', 'block' );
  });

  $('#recall_close, #recall_bg').click( function() {
    $('#recall').css( 'display', 'none' );
    $('#recall_bg').css( 'display', 'none' );
  });


  // Обрабатывает клик по кнопке "Задать вопрос" в сайдбаре
  // $('#ask_question').click( function( e ) {
  //   e.preventDefault();

  //   window.location.href = $(this).data( 'url' );
  // });


  // Обработка радио-кнопок на странице "Заказать документ"
  $('#business_label, #radio_text1').click( function( e ) {
    $('#business').prop('checked', true);
    $('#type')
      .empty()
      .prop( 'disabled', false )
      .append( $( '<option value="Регистрация ООО" selected>Регистрация ООО</option>' +
        '<option value="Внесение изменений в учредительные документы">Внесение изменений в учредительные документы</option> ' +
        '<option value="Регистрация ИП">Регистрация ИП</option> ' +
        '<option value="Регистрация ТСЖ">Регистрация ТСЖ</option> ' +
        '<option value="Другое">Другое</option>') );
  });

  $('#contract_label, #radio_text2').click( function( e ) {
    $('#contract').prop('checked', true);
    $('#type')
      .empty()
      .prop( 'disabled', false )
      .append( $( '<option value="Трудовой договор" selected>Трудовой договор</option>' +
        '<option value="Договор купли-продажи">Договор купли-продажи</option> ' +
        '<option value="Договор на оказание услуг">Договор на оказание услуг</option> ' +
        '<option value="Договор дарения">Договор дарения</option> ' +
        '<option value="Договор аренды">Договор аренды</option> ' +
        '<option value="Другое">Другое</option>') );
  });

  $('#court_label, #radio_text3').click( function( e ) {
    $('#court').prop('checked', true);
    $('#type')
      .empty()
      .prop( 'disabled', false )
      .append( $( '<option value="Исковое заявление" selected>Исковое заявление</option>' +
        '<option value="Отзыв или возражение на исковое заявление">Отзыв или возражение на исковое заявление</option> ' +
        '<option value="Ходатайство">Ходатайство</option> ' +
        '<option value="Жалоба на решение суда">Жалоба на решение суда</option> ' +
        '<option value="Жалоба на постановление по делу об административном правонарушении">Жалоба на постановление по делу об административном правонарушении</option> ' +
        '<option value="Другое">Другое</option>') );
  });

  $('#claim_label, #radio_text4').click( function( e ) {
    $('#claim').prop('checked', true);
    $('#type')
      .empty()
      .prop( 'disabled', false )
      .append( $( '<option value="Претензия на возврат денежных средств за товар (услугу) ненадлежащего качества" selected>Претензия на возврат денежных средств за товар (услугу) ненадлежащего качества</option>' +
        '<option value="Претензия в страховую компанию">Претензия в страховую компанию</option>' +
        '<option value="Претензия в банк">Претензия в банк</option>' +
        '<option value="Претензия к ЖКХ, управляющей компании">Претензия к ЖКХ, управляющей компании</option>' +
        '<option value="Претензия к застройщику">Претензия к застройщику</option>' +
        '<option value="Другое">Другое</option>') );
  });

  $('#complaint_label, #radio_text5').click( function( e ) {
    $('#complaint').prop('checked', true);
    $('#type')
      .empty()
      .prop( 'disabled', false )
      .append( $( '<option value="Жалоба на действия должностного лица" selected>Жалоба на действия должностного лица</option>' +
        '<option value="Жалоба на действия судебного пристава-исполнителя">Жалоба на действия судебного пристава-исполнителя</option> ' +
        '<option value="Жалоба на действия сотрудника ГИБДД">Жалоба на действия сотрудника ГИБДД</option> ' +
        '<option value="Другое">Другое</option>') );
  });

  $('#other_label, #radio_text6').click( function( e ) {
    $('#other').prop('checked', true);
    $('#type')
      .empty()
      .attr( 'disabled', 'disabled' )
      .append( $('<option>Не нужно указывать</option>') );
  });


  // Кнопка "Открыть все услуги"
  $('#services__switch').click( function(e) {
    var str = 'Открыть все услуги';
    var textbox = $('#services__switch-text');
    var services_container = $('.services__container');

    var rowOneHeight = $('.services-menu__row-one').height();
    var rowTwoHeight = $('.services-menu__row-two').height();

    var totalHeight = rowOneHeight + rowTwoHeight + 113;

    if( textbox.text() == str) {
      textbox.text('Скрыть все услуги');
      services_container.animate({height: totalHeight}, 300);
    } else {
      textbox.text('Открыть все услуги');
      services_container.animate({height: '282px'}, 300);
    }
  });


  // Гамбургер
  $('#hamburger').click( function( e ) {
    e.preventDefault();

    $('#mob-menu_bg').css( 'display', 'block' );
    $('#mob-menu').css( 'display', 'block' );
  });

  $('#mob_close, #mob-menu_bg').click( function() {
    $('#mob-menu').css( 'display', 'none' );
    $('#mob-menu_bg').css( 'display', 'none' );
  });


  // Настройка jQuery плагина Inputmask -- https://github.com/RobinHerbots/Inputmask
  $('#tel, #phone, #yourphone').inputmask({
    mask: '8 (999) 999-99-99[9999]',
    greedy: false,
    // clearIncomplete: true,
  });


  // Настройка jQuery плагина LightBox -- http://lokeshdhakar.com/projects/lightbox2/
  lightbox.option({
    'showImageNumberLabel': false
  });

});
