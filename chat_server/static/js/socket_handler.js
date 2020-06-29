const socket = io.connect("http://192.168.1.201:5000");

socket.on("connect", function () {
  console.log("Socket Connected...");
  console.log({
    username: appConfig.username,
    room: appConfig.room,
  });
  socket.emit("join_legal_room", {
    username: appConfig.username,
    room: appConfig.room,
  });
});
socket.on("join_legal_room_ack", function (data) {
  console.log(data);
});
socket.on("new_join_legal_ack", function (users) {
  users.forEach((user) => {
    user["hrefid"] = `#${user["uid"]}`;
  });
  console.log(users);

  $("#template-container").loadTemplate($("#template"), users);
  users.forEach((user) => {
    assign_btn = document.getElementById(user["ticket_id"]);
    assign_btn.onclick = function () {
      console.log(window.location.origin + "/chat_handler/" + this.id);
      var win = window.open(
        window.location.origin + "/chat_handler/" + this.id,
        "_blank"
      );
      win.focus();
    };
    pass_form = document.getElementById("pass_form_btn");
    pass_form.onclick = function () {
      legals = document.getElementsByName(user["ticket_id"]);
      for (let l = 0; l < legals.length; l++) {
        if (legals[l].checked) {
          console.log(legals[l].value);
          socket.emit("pass_query_legal", {
            from: appConfig.room,
            to: legals[l].value,
            ticket_id: this.name,
          });
        }
      }
      console.log("passed");
    };
  });
});

socket.on("disconnection_ack", function (username, id, active_users) {
  console.log(
    `${id} : ${username}    disconnected | Active Users : ${active_users}`
  );
});
